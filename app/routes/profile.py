import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.profile import ProfileRequest, ProfileResponse
from app.services.profile_service import ProfileService
from app.exceptions import (
    InvalidURLError,
    LinkedInAuthError,
    LinkedInBlockedError,
    LinkedInClientError,
    LinkedInRateLimitError,
    ProfileNotFoundError,
    ProfileServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter()
profile_service = ProfileService()

rate_limit_str = os.environ.get("RATE_LIMIT_DEFAULT", "10/minute")


def _rate_key(request: Request) -> str:
    return get_remote_address(request) if request.client else "local"


limiter = Limiter(key_func=_rate_key)

# exception type -> (status, client-facing message or None to use the exception text)
_STATUS_MAP = [
    (InvalidURLError, 400, None),
    (ProfileNotFoundError, 404, None),
    (LinkedInAuthError, 401, None),
    (LinkedInRateLimitError, 429, "LinkedIn rate limit exceeded. Try again later."),
    (LinkedInBlockedError, 503, "LinkedIn is challenging this session (CAPTCHA). Refresh the cookie."),
    (LinkedInClientError, 502, "Upstream error contacting LinkedIn."),
    (ProfileServiceError, 502, None),
]


async def _resolve(url: str, li_at=None, jsessionid=None, full: bool = False) -> ProfileResponse:
    try:
        return await profile_service.get_profile(url, li_at=li_at, jsessionid=jsessionid, full=full)
    except Exception as exc:  # noqa: BLE001 - deliberately mapped below
        for exc_type, status, message in _STATUS_MAP:
            if isinstance(exc, exc_type):
                raise HTTPException(status_code=status, detail=message or str(exc))
        raise


@router.post("/profile", response_model=ProfileResponse)
@limiter.limit(rate_limit_str)
async def get_profile_post(request: Request, body: ProfileRequest):
    logger.info("POST /profile url=%s full=%s", body.url, body.full)
    return await _resolve(body.url, body.li_at, body.jsessionid, body.full)


@router.get("/profile", response_model=ProfileResponse)
@limiter.limit(rate_limit_str)
async def get_profile_get(
    request: Request,
    url: str = Query(..., description="A public LinkedIn profile URL"),
    li_at: str = Query(None, description="Optional per-request session cookie"),
    jsessionid: str = Query(None),
    full: bool = Query(False, description="Also fetch complete skill/language/cert/etc. lists"),
):
    logger.info("GET /profile url=%s full=%s", url, full)
    return await _resolve(url, li_at, jsessionid, full)


@router.get("/health")
async def health_check():
    return {"status": "ok", "session_configured": bool(os.environ.get("LINKEDIN_LI_AT"))}
