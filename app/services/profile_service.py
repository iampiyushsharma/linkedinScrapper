import logging
import os
import re
from typing import Optional
from urllib.parse import unquote, urlparse

from cachetools import TTLCache

from app.linkedin.client import LinkedInClient
from app.linkedin.parser import LinkedInParser
from app.models.profile import ProfileResponse
from app.exceptions import InvalidURLError, ProfileNotFoundError

logger = logging.getLogger(__name__)

# /in/<slug> with optional locale prefix, trailing slash, query/fragment.
_SLUG_RE = re.compile(r"/in/([^/?#]+)", re.IGNORECASE)


class ProfileService:
    def __init__(self):
        self.client = LinkedInClient()
        ttl = int(os.environ.get("PROFILE_CACHE_TTL", "3600"))
        self.cache: TTLCache = TTLCache(maxsize=1000, ttl=ttl)

    @staticmethod
    def extract_identifier(url: str) -> str:
        """``https://www.linkedin.com/in/john-doe/`` -> ``john-doe``. Validates the
        host and rejects company / school / feed URLs."""
        if not url or not isinstance(url, str):
            raise InvalidURLError("A LinkedIn profile URL is required")

        candidate = url.strip()
        if "://" not in candidate:
            candidate = "https://" + candidate

        host = (urlparse(candidate).hostname or "").lower()
        if host != "linkedin.com" and not host.endswith(".linkedin.com"):
            raise InvalidURLError("URL host must be linkedin.com")

        match = _SLUG_RE.search(urlparse(candidate).path)
        if not match:
            raise InvalidURLError("Only personal profile URLs (linkedin.com/in/...) are supported")

        slug = unquote(match.group(1)).strip()
        if not slug:
            raise InvalidURLError("Could not read a profile identifier from the URL")
        return slug

    async def get_profile(
        self,
        url: str,
        li_at: Optional[str] = None,
        jsessionid: Optional[str] = None,
        full: bool = False,
    ) -> ProfileResponse:
        public_id = self.extract_identifier(url)

        cache_key = f"profile:{public_id.lower()}:{'full' if full else 'basic'}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info("Cache hit for %s", public_id)
            return cached

        logger.info("Fetching %s from LinkedIn (full=%s)", public_id, full)
        raw = await self.client.get_profile(
            public_id, li_at=li_at, jsessionid=jsessionid, full=full
        )
        if not raw or "data" not in raw:
            raise ProfileNotFoundError(f"Profile '{public_id}' not found or not accessible")

        try:
            response = LinkedInParser(raw).parse()
        except ValueError as e:
            raise ProfileNotFoundError(
                f"Profile '{public_id}' returned no usable data ({e})"
            ) from e

        self.cache[cache_key] = response
        return response
