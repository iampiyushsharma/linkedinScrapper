from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import logging

from app.models.profile import ProfileRequest, ProfileResponse
from app.services.profile_service import ProfileService
from app.exceptions import ProfileServiceError, ProfileNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()
profile_service = ProfileService()

# Configure the rate limiter for the profile endpoint based on env variable
rate_limit_str = os.environ.get("RATE_LIMIT_DEFAULT", "10/minute")
limiter = Limiter(key_func=get_remote_address)

@router.post("/profile", response_model=ProfileResponse)
@limiter.limit(rate_limit_str)
async def get_profile(request: Request, profile_req: ProfileRequest):
    """
    Retrieves and parses a LinkedIn profile based on the provided URL.
    """
    logger.info(f"Received request for URL: {profile_req.url}")
    try:
        profile_response = await profile_service.get_profile(profile_req.url)
        return profile_response
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProfileServiceError as e:
        err_str = str(e)
        if "rate limit" in err_str.lower():
            raise HTTPException(status_code=429, detail="LinkedIn rate limit exceeded. Please try again later.")
        elif "invalid" in err_str.lower() and "url" in err_str.lower():
            raise HTTPException(status_code=400, detail=err_str)
        elif "authentication" in err_str.lower() or "credentials" in err_str.lower() or "session expired" in err_str.lower():
             raise HTTPException(status_code=500, detail="Internal server configuration error (LinkedIn Authentication Failed).")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok"}
