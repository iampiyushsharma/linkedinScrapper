# app/exceptions.py

# --- LinkedIn Client Exceptions ---

class LinkedInClientError(Exception):
    """Base class for exceptions raised by the LinkedIn HTTP Client."""
    pass

class LinkedInRateLimitError(LinkedInClientError):
    """Raised when LinkedIn responds with a 429 Rate Limit Exceeded."""
    pass

class LinkedInAuthError(LinkedInClientError):
    """Raised when LinkedIn responds with a 401 or 403 Authentication error."""
    pass


# --- Profile Service Exceptions ---

class ProfileServiceError(Exception):
    """Base class for exceptions raised by the Profile Service."""
    pass

class ProfileNotFoundError(ProfileServiceError):
    """Raised when a profile cannot be found or is inaccessible."""
    pass
