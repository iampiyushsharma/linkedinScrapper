import re
import os
import logging
from cachetools import TTLCache
from typing import Dict, Any

from app.linkedin.client import LinkedInClient
from app.linkedin.parser import LinkedInParser
from app.models.profile import ProfileResponse
from app.exceptions import LinkedInClientError, ProfileServiceError, ProfileNotFoundError

logger = logging.getLogger(__name__)

class ProfileService:
    # Pre-compile regex for performance
    URL_PATTERN = re.compile(r"linkedin\.com/in/([^/?#]+)")

    def __init__(self):
        self.client = LinkedInClient()
        
        # Configure cache TTL from environment variables
        ttl = int(os.environ.get("PROFILE_CACHE_TTL", 3600))
        # Use an in-memory TTL Cache
        self.cache = TTLCache(maxsize=1000, ttl=ttl)

    def _extract_identifier(self, url: str) -> str:
        """
        Extracts the profile identifier (slug) from a standard LinkedIn URL.
        Example: https://www.linkedin.com/in/example-user/ -> example-user
        """
        match = self.URL_PATTERN.search(url)
        if match:
            return match.group(1).strip()
        raise ValueError("Invalid LinkedIn profile URL")

    async def get_profile(self, url: str) -> ProfileResponse:
        """
        Gets the profile either from the cache or by making a request to LinkedIn.
        """
        try:
            public_identifier = self._extract_identifier(url)
        except ValueError as e:
            raise ProfileServiceError(str(e))

        # Check cache
        cache_key = f"profile:{public_identifier}"
        cached_response = self.cache.get(cache_key)
        
        if cached_response:
            logger.info(f"Cache hit for {public_identifier}")
            return cached_response
            
        logger.info(f"Cache miss for {public_identifier}. Fetching from LinkedIn.")
        
        # Fetch from LinkedIn
        try:
            raw_data = await self.client.get_profile(public_identifier)
        except LinkedInClientError as e:
            # We treat client errors (like auth, rate limits) as service errors to bubble up to the API layer
            raise ProfileServiceError(str(e))
            
        # Ensure we have data
        if not raw_data or "data" not in raw_data:
            raise ProfileNotFoundError(f"Profile {public_identifier} not found or inaccessible.")
            
        # Parse
        try:
            parser = LinkedInParser(raw_data)
            profile_response = parser.parse()
        except ValueError as e:
            logger.error(f"Failed to parse profile {public_identifier}: {e}")
            raise ProfileServiceError(f"Parsing failed: {e}")
            
        # Store in cache
        self.cache[cache_key] = profile_response
        
        return profile_response
