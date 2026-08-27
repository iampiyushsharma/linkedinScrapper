# LinkedIn Profile Scraper API

This project provides a robust, browserless API for retrieving public LinkedIn profile data as structured JSON. It directly communicates with LinkedIn's internal HTTP endpoints.

## Overview
This API takes a LinkedIn profile URL (e.g., `https://www.linkedin.com/in/example/`), parses the profile identifier, and uses LinkedIn's internal Voyager REST API to retrieve and structure the profile's data, including basic info, experience, education, skills, certifications, and languages.

**Note on PhantomBuster**: The hiring assignment referenced PhantomBuster as a functional benchmark. This implementation operates entirely independently. It does not use PhantomBuster, call PhantomBuster APIs, or depend on it in any way. All data is retrieved directly from LinkedIn via pure HTTP requests.

## Architecture

The system is built on a clean, production-oriented backend architecture:
- **FastAPI**: Provides a fast, modern API layer with automatic validation.
- **Pydantic**: Validates incoming requests and structures the outgoing JSON response.
- **HTTPX**: Used for asynchronous, direct HTTP communication with LinkedIn endpoints.
- **Cachetools**: Provides an in-memory TTL caching mechanism to reduce redundant external calls.
- **SlowAPI**: Implements robust rate limiting to protect the endpoints.

**Request Flow:**
`Client -> POST /profile -> Validation -> Rate Limiter -> Cache Check -> LinkedIn HTTP Client -> Voyager API -> Graph Parser -> Cache Store -> Normalized JSON Response`

## Reverse Engineering Approach

The core requirement of this project was to avoid using a browser (Selenium, Playwright, Puppeteer). 

### Endpoint Selection
Through HTTP inspection, we bypassed the legacy `/voyager/api/identity/profiles/{id}/profileView` endpoint in favor of the modern, internal dashboard endpoint:
`https://www.linkedin.com/voyager/api/identity/dash/profiles`

This endpoint is superior because it returns highly structured graph JSON and responds to specific `decorationId` query parameters to retrieve full profile entities.

### Authentication
LinkedIn requires an active session to query this endpoint. The HTTP client injects:
- `li_at`: The primary authentication session cookie.
- `JSESSIONID`: The session identifier.
- `csrf-token`: A required header extracted directly from the `JSESSIONID`.

### Parser Logic
Rather than relying on fixed indices (which break easily), our parser treats the LinkedIn response as an entity graph:
1. It builds an index `entityUrn -> entity` from the `included` array.
2. It resolves root references (like `*experience`, `*education`) by traversing the URNs.
3. This creates a highly resilient parser that handles missing fields, partial responses, and unexpected ordering gracefully.

## Setup Instructions

### Environment Variables
Copy the sample environment file and add your LinkedIn credentials:
```bash
cp .env.example .env
```
Ensure you populate `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` using values from a logged-in browser session. 
*Note: Do NOT commit this `.env` file or hardcode these credentials anywhere.*

### Running Locally
You can run the API locally using `uvicorn`:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Testing
Unit and integration tests are provided using `pytest` and mocked JSON responses to avoid hitting LinkedIn during test runs.
```bash
pytest tests/
```

## API Documentation

### `POST /profile`
Retrieves a structured LinkedIn profile.

**Request:**
```json
{
  "url": "https://www.linkedin.com/in/example/"
}
```

**Response (200 OK):**
```json
{
  "profile": {
    "name": "John Doe",
    "headline": "Software Engineer",
    "location": "San Francisco, CA",
    "about": "Passionate about building scalable systems.",
    "profile_url": "https://www.linkedin.com/in/example",
    "profile_image": "https://media.licdn.com/dms/image/..."
  },
  "experience": [...],
  "education": [...],
  "skills": [...],
  "certifications": [...],
  "languages": [...]
}
```

### `GET /health`
Health check endpoint.

## Security & Reliability

- **Rate Limiting**: The public API endpoints are protected using `slowapi`. The default limit is `10 requests/minute` (configurable via `RATE_LIMIT_DEFAULT`).
- **Caching**: Successful profile retrievals are cached in-memory for 1 hour by default (configurable via `PROFILE_CACHE_TTL`). Cached data may be stale until the TTL expires, but this significantly reduces the load on LinkedIn and lowers the risk of account suspension.
- **Credential Protection**: Credentials are not logged, exposed in error messages, or cached. 
- **LinkedIn Rate Limits**: The client respects LinkedIn's own HTTP 429 responses and does not attempt to bypass CAPTCHAs or MFA.

## Known Limitations
- **Account Bans**: Relying on internal Voyager APIs with a personal `li_at` cookie carries a risk of LinkedIn flagging or restricting the account if request volume is too high.
- **Endpoint Instability**: LinkedIn frequently updates its internal APIs. Changes to the `decorationId` or response JSON structure might require parser updates.
- **Cache Staleness**: Due to the TTL cache, recent profile changes might not be instantly reflected in the API response.
