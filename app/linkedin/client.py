import httpx
import logging
import os
import orjson
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.linkedin.endpoints import LinkedInEndpoints
from app.exceptions import LinkedInClientError, LinkedInRateLimitError, LinkedInAuthError

logger = logging.getLogger(__name__)

def is_transient_error(exception: BaseException) -> bool:
    """Returns True if the exception should trigger a retry."""
    # Do not retry on Auth or Rate Limit errors
    if isinstance(exception, (LinkedInAuthError, LinkedInRateLimitError)):
        return False
    # Retry on other generic LinkedInClientError (like 502 Bad Gateway, Timeout, etc.)
    return isinstance(exception, LinkedInClientError)

class LinkedInClient:
    def __init__(self):
        self.li_at = os.environ.get("LINKEDIN_LI_AT")
        self.jsessionid = os.environ.get("LINKEDIN_JSESSIONID")
        self.session: Optional[httpx.AsyncClient] = None
        
        if not self.li_at or not self.jsessionid:
            logger.warning("LinkedIn credentials missing from environment.")
            
    def _get_headers(self) -> Dict[str, str]:
        # Extract CSRF token from JSESSIONID (remove quotes if present)
        csrf_token = self.jsessionid.strip('"') if self.jsessionid else ""
        
        return {
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "csrf-token": csrf_token,
            "x-restli-protocol-version": "2.0.0",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
    def _get_cookies(self) -> Dict[str, str]:
        return {
            "li_at": self.li_at,
            "JSESSIONID": self.jsessionid,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_transient_error),
        reraise=True
    )
    async def get_profile(self, public_identifier: str) -> Dict[str, Any]:
        """
        Fetches the raw profile JSON graph from the Voyager API.
        Automatically retries on transient network failures or 5xx server errors.
        """
        if not self.li_at or not self.jsessionid:
            raise LinkedInAuthError("LinkedIn credentials are not configured.")

        url = f"{LinkedInEndpoints.BASE_URL}{LinkedInEndpoints.DASH_PROFILES}"
        
        params = {
            "q": "memberIdentity",
            "memberIdentity": public_identifier,
            "decorationId": LinkedInEndpoints.DECORATION_ID
        }
        
        headers = self._get_headers()
        cookies = self._get_cookies()
        
        try:
            if self.session is None:
                self.session = httpx.AsyncClient(timeout=15.0)

            response = await self.session.get(url, params=params, headers=headers, cookies=cookies)
            
            if response.status_code == 429:
                logger.error("LinkedIn rate limit exceeded (429).")
                raise LinkedInRateLimitError("LinkedIn rate limit exceeded.")
            elif response.status_code == 401 or response.status_code == 403:
                logger.error(f"LinkedIn authentication failed ({response.status_code}).")
                raise LinkedInAuthError("LinkedIn session expired or invalid.")
            
            response.raise_for_status()
            try:
                return orjson.loads(response.content)
            except orjson.JSONDecodeError:
                logger.error("LinkedIn returned a non-JSON response (possibly a CAPTCHA or auth wall).")
                raise LinkedInClientError("Received invalid JSON from LinkedIn. The account may be restricted or challenged.")
                
        except httpx.RequestError as e:
            logger.error(f"Network error communicating with LinkedIn: {e}")
            raise LinkedInClientError("Failed to connect to LinkedIn API.")
        except httpx.HTTPStatusError as e:
            logger.error(f"LinkedIn API returned error status: {e.response.status_code}")
            raise LinkedInClientError(f"LinkedIn API error: {e.response.status_code}")
