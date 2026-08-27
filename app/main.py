from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from dotenv import load_dotenv
import logging

# Load environment variables early
load_dotenv()

from app.routes.profile import router as profile_router, limiter

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="LinkedIn Profile Scraper API",
    description="A reverse-engineered API to retrieve public LinkedIn profiles as structured JSON.",
    version="1.0.0"
)

# Register rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routes
app.include_router(profile_router)
