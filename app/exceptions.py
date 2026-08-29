"""Typed exceptions. Each maps cleanly to one HTTP status in the route layer."""


# --- LinkedIn client layer ---------------------------------------------------

class LinkedInClientError(Exception):
    """Transient failure talking to LinkedIn (network error, 5xx). Retryable."""


class LinkedInRateLimitError(LinkedInClientError):
    """LinkedIn returned HTTP 429."""


class LinkedInAuthError(LinkedInClientError):
    """The session cookie is missing, expired, or rejected (401/403/999/redirect)."""


class LinkedInBlockedError(LinkedInClientError):
    """LinkedIn served a challenge / CAPTCHA / non-JSON wall. Not retryable."""


# --- Profile service layer -------------------------------------------------

class ProfileServiceError(Exception):
    """Generic upstream failure surfacing from the service."""


class InvalidURLError(ProfileServiceError):
    """The supplied string is not a LinkedIn personal-profile URL."""


class ProfileNotFoundError(ProfileServiceError):
    """Profile does not exist or is not visible to the session."""
