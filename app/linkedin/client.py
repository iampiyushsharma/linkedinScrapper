import asyncio
import logging
import os
import random
from typing import Any, Dict, List, Optional

import httpx
import orjson
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.linkedin.endpoints import LinkedInEndpoints
from app.exceptions import (
    LinkedInAuthError,
    LinkedInBlockedError,
    LinkedInClientError,
    LinkedInRateLimitError,
)

logger = logging.getLogger(__name__)

_BASE_HEADERS = {
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
}


def _generate_jsessionid() -> str:
    """Mint a JSESSIONID / csrf value. Voyager only checks that this cookie equals
    the `csrf-token` header, so with a valid `li_at` we can generate it."""
    return "ajax:" + "".join(random.choices("0123456789", k=19))


def _clean(value: Optional[str]) -> str:
    return (value or "").strip().strip('"')


def _is_retryable(exc: BaseException) -> bool:
    """Retry only genuine transient failures - not auth, rate-limit, or blocks."""
    return isinstance(exc, LinkedInClientError) and not isinstance(
        exc, (LinkedInAuthError, LinkedInRateLimitError, LinkedInBlockedError)
    )


class LinkedInClient:
    """Thin async HTTP client for LinkedIn's Voyager API."""

    def __init__(self):
        self.li_at = os.environ.get("LINKEDIN_LI_AT")
        self.jsessionid = os.environ.get("LINKEDIN_JSESSIONID")
        timeout = float(os.environ.get("LINKEDIN_TIMEOUT", "15"))
        self._http = httpx.AsyncClient(http2=True, timeout=timeout, follow_redirects=False)

        if not self.li_at:
            logger.warning("No LINKEDIN_LI_AT set; requests must supply 'li_at'.")

    # ------------------------------------------------------------------ internals
    def _resolve_creds(self, li_at: Optional[str], jsessionid: Optional[str]):
        li_at = _clean(li_at) or _clean(self.li_at)
        if not li_at:
            raise LinkedInAuthError(
                "No LinkedIn li_at cookie. Set LINKEDIN_LI_AT on the server or pass "
                "'li_at' in the request body."
            )
        csrf = _clean(jsessionid) or _clean(self.jsessionid) or _generate_jsessionid()
        return li_at, csrf

    async def _request(self, path: str, params: dict, li_at: str, csrf: str) -> Optional[Dict[str, Any]]:
        headers = {**_BASE_HEADERS, "csrf-token": csrf}
        cookies = {"li_at": li_at, "JSESSIONID": f'"{csrf}"'}

        try:
            resp = await self._http.get(
                f"{LinkedInEndpoints.BASE_URL}{path}", params=params, headers=headers, cookies=cookies
            )
        except httpx.RequestError as e:
            raise LinkedInClientError(f"Network error contacting LinkedIn: {e}") from e

        code = resp.status_code
        if code == 200:
            if "json" not in resp.headers.get("content-type", ""):
                raise LinkedInBlockedError("LinkedIn served an HTML wall instead of JSON.")
            try:
                return orjson.loads(resp.content)
            except orjson.JSONDecodeError as e:
                raise LinkedInBlockedError("LinkedIn returned an undecodable response.") from e
        if code in (404, 410):
            return None
        if code == 429:
            raise LinkedInRateLimitError("LinkedIn rate limit exceeded (429).")
        if code in (301, 302, 303, 307, 308, 401, 403, 999):
            raise LinkedInAuthError(f"LinkedIn rejected the session (HTTP {code}).")
        raise LinkedInClientError(f"LinkedIn returned HTTP {code}.")

    # ------------------------------------------------------------------ public
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    async def get_profile(
        self,
        public_identifier: str,
        li_at: Optional[str] = None,
        jsessionid: Optional[str] = None,
        full: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch the profile graph and return one normalized ``{data, included}`` doc.

        The primary ``dash/profiles`` call already carries the profile, positions,
        educations, companies, and a capped set of skills / projects /
        certifications. With ``full=True`` the per-section collections (complete
        skills, languages, certifications, volunteering, honors, projects) are
        fetched sequentially and merged in. Section failures are non-fatal.

        Retries only genuine transient errors (network / 5xx) - never auth,
        rate-limit, or challenge responses.
        """
        li_at, csrf = self._resolve_creds(li_at, jsessionid)

        primary = await self._request(
            LinkedInEndpoints.DASH_PROFILES,
            {
                "q": "memberIdentity",
                "memberIdentity": public_identifier,
                "decorationId": LinkedInEndpoints.DECORATION_ID,
            },
            li_at,
            csrf,
        )
        if not primary or "data" not in primary:
            return primary or {}

        elements = (primary.get("data") or {}).get("*elements") or []
        root_urn = elements[0] if elements else None

        merged: Dict[str, Any] = {
            "data": primary["data"],
            "included": list(primary.get("included") or []),
        }
        if full and root_urn:
            merged["included"].extend(await self._fetch_sections(root_urn, li_at, csrf))
        return merged

    async def _fetch_sections(self, root_urn: str, li_at: str, csrf: str) -> List[Dict[str, Any]]:
        """Fetch per-section collections one at a time (a parallel burst trips
        LinkedIn's abuse detection). Stops early if the session gets rejected."""
        entities: List[Dict[str, Any]] = []
        for path in LinkedInEndpoints.SECTION_ENDPOINTS.values():
            try:
                data = await self._request(
                    path, {"q": "viewee", "profileUrn": root_urn, "count": 100}, li_at, csrf
                )
                entities.extend((data or {}).get("included") or [])
            except LinkedInAuthError:
                logger.warning("Session rejected during section fetch; returning partial data.")
                break
            except LinkedInClientError as e:
                logger.info("Section %s unavailable: %s", path, e)
            await asyncio.sleep(0.4)
        return entities

    async def close(self) -> None:
        await self._http.aclose()
