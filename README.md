# LinkedIn Profile API

A hosted HTTPS API that takes a LinkedIn profile URL and returns the profile as
structured JSON — name, headline, location, about, experience, education, skills,
certifications, languages, projects, honors, volunteering and images.

**Purely reverse-engineered and browserless.** The service replays LinkedIn's own
internal ("Voyager") HTTP endpoints with a session cookie. No Selenium /
Puppeteer / Playwright / headless Chromium anywhere.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your LINKEDIN_LI_AT
uvicorn app.main:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/profile \
  -H 'content-type: application/json' \
  -d '{"url": "https://www.linkedin.com/in/williamhgates"}'
```

Interactive docs: <http://127.0.0.1:8000/docs>

### Getting `li_at`

Log into linkedin.com, open DevTools → **Application → Cookies → linkedin.com**,
copy the **`li_at`** value. That's the whole session — keep it secret. `JSESSIONID`
is optional (the service generates a matching CSRF value when it's absent).

---

## API

### `POST /profile` · `GET /profile`

| field | in | required | description |
|---|---|---|---|
| `url` | body / `?url=` | ✅ | a `linkedin.com/in/<slug>` URL (any locale sub-domain, trailing slash, query string) |
| `li_at` | body / `?li_at=` | – | per-request session cookie; overrides `LINKEDIN_LI_AT` for this call |
| `jsessionid` | body / `?jsessionid=` | – | pair with `li_at`; generated if omitted |
| `full` | body / `?full=true` | – | also fetch the **complete** skills / languages / certifications / volunteering / honors / projects lists (6 extra requests, one at a time, ~5–8 s). Default `false` returns a single request — the primary call still includes ~20 skills plus projects and certifications. |

```bash
# use a caller-supplied session, and fetch everything
curl -X POST http://127.0.0.1:8000/profile -H 'content-type: application/json' \
  -d '{"url":"https://www.linkedin.com/in/williamhgates","li_at":"AQEDA...","full":true}'

# or as a GET
curl "http://127.0.0.1:8000/profile?url=https://www.linkedin.com/in/williamhgates"
```

#### Response `200`

```jsonc
{
  "profile": {
    "name": "Bill Gates",
    "first_name": "Bill",
    "last_name": "Gates",
    "headline": "Chair, Gates Foundation and Founder, Breakthrough Energy",
    "location": "Seattle, Washington, United States",
    "country": "United States",
    "industry": "Philanthropy",
    "about": "Chair of the Gates Foundation...",
    "public_identifier": "williamhgates",
    "profile_url": "https://www.linkedin.com/in/williamhgates",
    "member_id": "251749025",
    "is_premium": false,
    "is_influencer": true,
    "profile_image": "https://media.licdn.com/dms/image/.../800_800/...",
    "background_image": "https://media.licdn.com/dms/image/.../..."
  },
  "experience": [
    {
      "company": "Breakthrough Energy",
      "company_url": "https://www.linkedin.com/company/breakthrough-energy/",
      "company_logo": "https://media.licdn.com/dms/image/.../200_200/...",
      "title": "Founder",
      "employment_type": null,
      "location": null,
      "description": null,
      "start_date": "2015",
      "end_date": null,
      "current": true
    }
  ],
  "education": [
    { "institution": "Harvard University", "institution_url": null, "institution_logo": null,
      "degree": null, "field_of_study": null, "description": null, "activities": null,
      "grade": null, "start_date": "1973", "end_date": "1975" }
  ],
  "skills":         [ { "name": "Philanthropy" } ],
  "certifications": [ { "name": "...", "issuer": "...", "license_number": null, "url": null,
                        "issue_date": "2020-09", "expiry_date": null } ],
  "languages":      [ { "name": "English", "proficiency": "NATIVE_OR_BILINGUAL" } ],
  "projects":       [ { "title": "...", "description": "...", "start_date": null, "end_date": null } ],
  "honors":         [ { "title": "...", "issuer": "...", "description": "...", "date": "1980" } ],
  "volunteer":      [ { "organization": "...", "role": "...", "cause": "EDUCATION",
                        "description": "...", "start_date": "2011-12", "end_date": null } ]
}
```

Dates are `"YYYY-MM"` or `"YYYY"`. Experience is ordered current-first, then newest.
Any field LinkedIn doesn't expose is `null` / `[]`.

#### Errors

| status | when |
|---|---|
| `400` | not a `linkedin.com/in/...` URL |
| `401` | no session cookie, or the cookie was rejected — supply a fresh `li_at` |
| `404` | profile doesn't exist / not visible to the session |
| `429` | per-IP rate limit, or LinkedIn returned 429 |
| `503` | LinkedIn served a CAPTCHA / challenge — refresh the cookie |
| `502` | other upstream error |

### `GET /health`

```json
{ "status": "ok", "session_configured": true }
```

---

## How it works

`linkedin.com` renders profiles by calling a private JSON API at
`/voyager/api/...`. This service calls the same endpoints. Auth is cookie-only:
`li_at` (the session) plus a `JSESSIONID` cookie that must equal the `csrf-token`
header — LinkedIn doesn't require it to be one it issued, so we mint it.

- **Primary call** — `GET /voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=<slug>&decorationId=FullProfileWithEntities-85`
  returns a normalized `{data, included}` entity graph: the profile, positions,
  educations, companies, schools, geo, industry, and a capped set of skills /
  projects / certifications.
- **`full=true`** adds six calls (`profileSkills`, `profileLanguages`,
  `profileCertifications`, `profileVolunteerExperiences`, `profileHonors`,
  `profileProjects`), fetched **one at a time** (a parallel burst trips LinkedIn's
  abuse detection) and merged into the same graph.
- **Parser** (`app/linkedin/parser.py`) indexes every entity by URN in one O(n)
  pass, finds the root profile, and resolves references — a position's
  `companyUrn` → the company's URL and logo, `geoLocation` → a readable location
  and country, `industryUrn` → the industry name, `employmentTypeUrn` → its label.

### Reliability

- **Retry** (`tenacity`): 3 attempts with exponential backoff — **only** on
  genuine transient failures (network errors, 5xx). Never retries auth,
  rate-limit, or challenge responses.
- **Rate limit** (`slowapi`): per client IP, `RATE_LIMIT_DEFAULT` (default
  `10/minute`) on `/profile`.
- **Cache** (`cachetools.TTLCache`): in-memory, keyed by profile + depth,
  `PROFILE_CACHE_TTL` (default 1 h). A cache hit skips LinkedIn entirely.
- One HTTP/2 connection kept alive and reused across calls; responses parsed with
  `orjson` and served via `ORJSONResponse`.

---

## Configuration

| var | default | purpose |
|---|---|---|
| `LINKEDIN_LI_AT` | – | backend session cookie (or pass `li_at` per request) |
| `LINKEDIN_JSESSIONID` | generated | CSRF cookie |
| `RATE_LIMIT_DEFAULT` | `10/minute` | per-IP `/profile` limit |
| `PROFILE_CACHE_TTL` | `3600` | cache lifetime, seconds |
| `LINKEDIN_TIMEOUT` | `15` | per-request timeout, seconds |

`.env` is git-ignored — no secret ever enters the repo.

---

## Deployment

`render.yaml` blueprint included: push to GitHub → Render → **New → Blueprint** →
set `LINKEDIN_LI_AT` in the dashboard → deploy (HTTPS + `/health` check).
Any Docker host works: `docker build -t li-api . && docker run -p 8000:8000 --env-file .env li-api`.
Image is `python:3.11-slim`, ~150 MB, no browser packages.

---

## Known limitations

- **Terms of Service.** Automated access is against LinkedIn's User Agreement —
  educational / evaluation use only. Use your own account, keep volume low.
- **Cloud-IP rejection.** A cookie minted on a home connection is often
  invalidated within a few requests when used from a datacenter IP (Render, AWS).
  Workarounds: pass a fresh `li_at` per request, or front the service with a
  residential proxy. A flagged account recovers after ~24–48 h of normal use.
- **Cookie lifetime.** Weeks-to-months from a stable IP; there is no
  auto-refresh — supply a new `li_at` (env or per request) when it dies.
- **Depth vs. safety.** The default call returns ~20 skills. `full=true` returns
  the complete lists but makes 7 requests instead of 1 — riskier for the session.
- **Only authenticated-visible data.** Public for everyone, more for 1st-degree
  connections. Contact info (email/phone) has no browserless endpoint.
- **Endpoint drift.** Undocumented internal endpoints; the `decorationId` version
  in particular may need bumping over time.
- **Cache staleness.** Up to `PROFILE_CACHE_TTL` before an edited profile updates.

---

## Tests & layout

```bash
pip install -r requirements-dev.txt
pytest        # 17 tests — parser, client (mocked HTTP), URL handling, API surface. No network.
```

```
app/
  main.py                       FastAPI app + lifespan + ORJSON responses
  models/profile.py             request + response schema (Pydantic)
  routes/profile.py             POST/GET /profile, /health, rate limiting, error→status map
  services/profile_service.py   URL parsing, caching, orchestration
  linkedin/
    endpoints.py                URLs + decoration id
    client.py                   async httpx client, retry, cookie handling
    parser.py                   normalized graph → schema
tests/  test_parser.py  test_client.py  test_api.py
```
