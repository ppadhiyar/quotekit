import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import get_settings
from .routers import chat, ingest, quote

logging.basicConfig(level=logging.INFO)

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)

app = FastAPI(
    title="QuoteKit API",
    description="Grounded quoting and Q&A with an evaluation gate.",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Demo UI and embedded widgets call from customer domains; the API holds no
# user credentials, so a permissive CORS policy is acceptable here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(quote.router)
app.include_router(chat.router)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    return {"status": "ok", "demo_mode": settings.demo_mode}
