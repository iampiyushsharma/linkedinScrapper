# LinkedIn Profile API

A blazing-fast, browserless REST API that reverse-engineers LinkedIn's internal endpoints to extract structured profile data (Experience, Education, Skills, etc.) in milliseconds.

## 🚀 Technical Highlights

Built to production standards, designed to survive LinkedIn's dynamic API and strict rate limits:
- **Lightning Fast**: Uses **HTTP Keep-Alive** pooling and **`orjson`** (Rust-based) to parse massive 500KB+ JSON graphs instantly.
- **O(1) Graph Parsing**: Profile entities are pre-grouped by type in a single pass (`defaultdict`), turning slow nested array scans into instant O(1) lookups.
- **Fault-Tolerant**: Implements **Exponential Backoff (`tenacity`)** to automatically retry transient network drops, while smartly halting on 401/429s to prevent account bans.
- **Protected**: Native rate-limiting (`slowapi`) and TTL caching (`cachetools`) defend against abuse and credential exhaustion.
- **Crash-Proof**: Safely intercepts silent HTML CAPTCHA traps and explicitly handles unexpected `null` schemas without throwing Exceptions.

## ⚙️ Reverse Engineering Approach
Instead of relying on heavy, slow headless browsers (Selenium/Puppeteer), this API acts as a direct HTTP client. It intercepts the internal Voyager API (`/voyager/api/identity/dash/profiles`) using hijacked session cookies (`li_at` and `JSESSIONID`), bypassing HTML scraping entirely to receive highly-structured JSON directly from LinkedIn's backend.

## 🛠️ Quick Start

### 1. Setup Environment
```bash
cp .env.example .env
```
Add your LinkedIn session cookies (`LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID`) to the `.env` file. Do NOT commit this file to GitHub.

### 2. Run the Server
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
*Docker support is included via the `Dockerfile` for seamless deployment.*

## 📖 API Usage

**POST** `/profile`
```bash
curl -X POST "http://127.0.0.1:8000/profile" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.linkedin.com/in/williamhgates"}'
```

**Response (200 OK):**
```json
{
  "profile": {
    "name": "Bill Gates",
    "headline": "Co-chair, Bill & Melinda Gates Foundation",
    "location": "Seattle, WA"
  },
  "experience": [...],
  "education": [...],
  "skills": [...]
}
```

## ⚠️ Known Limitations
- **Account Bans**: Relying on personal session cookies carries a risk of LinkedIn restricting the account if request volume is too high.
- **Cache Staleness**: Due to the TTL cache, recent profile updates may take up to 1 hour to reflect in the API.
