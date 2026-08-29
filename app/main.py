import logging
from contextlib import asynccontextmanager
from pathlib import Path

# slowapi's Limiter() eagerly builds Starlette's Config(".env"); make sure the
# file exists so a container without one doesn't crash on import.
try:
    Path(".env").touch(exist_ok=True)
except OSError:
    pass

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.routes.profile import limiter, profile_service, router as profile_router  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await profile_service.client.close()


app = FastAPI(
    title="LinkedIn Profile API",
    description="A browserless, reverse-engineered API that returns a LinkedIn profile as structured JSON.",
    version="2.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(profile_router)


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "LinkedIn Profile API", "docs": "/docs"}
