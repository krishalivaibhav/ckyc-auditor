"""
signals/security.py
-------------------
Security layer for the signals module API.

Implements:
  1. API Key authentication    — all endpoints require a valid key in the header
  2. Rate limiting             — prevents abuse (max N requests/minute per client)
  3. Input sanitisation        — strips HTML/injection characters from text inputs
  4. Sensitive data masking    — API keys are never written to logs
  5. Structured security logging — every auth failure is recorded
"""

import os
import re
import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

# ── Logger (structured, no secrets) ──────────────────────────────────────────
logger = logging.getLogger("signals.security")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# ── API Key Auth ──────────────────────────────────────────────────────────────
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_VALID_API_KEY  = os.getenv("SIGNALS_API_KEY", "signals-dev-key-change-in-production")


def require_api_key(api_key: str = Security(_API_KEY_HEADER)):
    """
    FastAPI dependency. Protects all endpoints behind an API key.
    Set SIGNALS_API_KEY in .env to change the key.
    """
    if not api_key:
        logger.warning("Request rejected — no API key provided in X-API-Key header.")
        raise HTTPException(status_code=401, detail="API key required. Set X-API-Key header.")
    if api_key != _VALID_API_KEY:
        # Log the masked key only (first 4 chars)
        masked = api_key[:4] + "****"
        logger.warning(f"Request rejected — invalid API key: {masked}")
        raise HTTPException(status_code=403, detail="Invalid API key.")
    return api_key


# ── Rate Limiter ──────────────────────────────────────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))   # per window
RATE_LIMIT_WINDOW   = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60")) # seconds


def check_rate_limit(request: Request):
    """
    FastAPI dependency. Enforces per-IP rate limiting.
    Default: 30 requests per 60 seconds.
    """
    client_ip = request.client.host if request.client else "unknown"
    now       = time.time()
    window    = now - RATE_LIMIT_WINDOW

    # Prune timestamps outside the window
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window]

    if len(_rate_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s."
        )

    _rate_store[client_ip].append(now)


# ── Input Sanitisation ────────────────────────────────────────────────────────
_DANGEROUS_PATTERN = re.compile(r"[<>{};\"'\\]")

def sanitise(text: str, max_length: int = 500) -> str:
    """
    Strip dangerous characters and enforce a max length.
    Prevents prompt injection and basic XSS in stored text.
    """
    if not isinstance(text, str):
        return ""
    cleaned = _DANGEROUS_PATTERN.sub("", text)
    return cleaned[:max_length].strip()


def mask_key(key: str) -> str:
    """Return a masked version of an API key safe to write to logs."""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]
