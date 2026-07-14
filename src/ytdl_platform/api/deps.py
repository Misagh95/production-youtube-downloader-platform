"""API dependencies and middleware."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from ytdl_platform.config import get_settings

logger = logging.getLogger(__name__)

# ── API Key Auth ──

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Depends(_api_key_header)) -> Optional[str]:
    """Verify the API key if one is configured."""
    settings = get_settings()
    if settings.api_key == "change-me-to-a-secure-random-string":
        # No real key configured — skip auth in development
        return None
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key


# ── CORS ──

def setup_cors(app) -> None:
    """Add CORS middleware to the FastAPI app."""
    settings = get_settings()
    origins = ["*"] if settings.app_env == "development" else [settings.public_base_url]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── Rate limiting (simple in-memory) ──

_rate_limits: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 30  # per window


def check_rate_limit(client_id: str) -> bool:
    """Simple in-memory rate limiter. Returns True if within limits."""
    now = time.time()
    if client_id not in _rate_limits:
        _rate_limits[client_id] = [now]
        return True

    # Clean old entries
    _rate_limits[client_id] = [
        t for t in _rate_limits[client_id] if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_rate_limits[client_id]) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    _rate_limits[client_id].append(now)
    return True


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for rate limiting."""
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait and try again.",
        )


# ── Concurrent job limiter ──

_active_jobs = 0


def can_start_job() -> bool:
    """Check if we can start a new download job."""
    settings = get_settings()
    return _active_jobs < settings.max_concurrent_jobs


def increment_active_jobs() -> None:
    global _active_jobs
    _active_jobs += 1


def decrement_active_jobs() -> None:
    global _active_jobs
    _active_jobs = max(0, _active_jobs - 1)
