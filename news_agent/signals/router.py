"""
signals/router.py
-----------------
FastAPI router for the signals package.

Security applied to ALL endpoints:
  - API Key authentication (X-API-Key header)
  - Per-IP rate limiting
  - Input sanitisation on all string parameters

Endpoints:
  Watchlist management   → add, remove, list entities
  Scan control           → trigger, update frequency, status
  Results                → view signals, audit log from DB
  Health                 → liveness check
"""

import os
import threading
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from apscheduler.schedulers.background import BackgroundScheduler
from .models import WatchedEntity, Signal
from . import kyc_list, scanner
from .database import (
    init_db, get_all_signals, get_audit_log,
    get_signals_for_entity, count_articles_scanned, count_signals_emitted
)
from .security import require_api_key, check_rate_limit, sanitise

logger   = logging.getLogger("signals.router")
router   = APIRouter(prefix="/signals", tags=["Signals — Adverse Media"])

# Shared scheduler
_scheduler             = BackgroundScheduler()
_scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))

# Common dependencies applied to all endpoints
_DEPS = [Depends(check_rate_limit), Depends(require_api_key)]


@router.on_event("startup")
def start_up():
    global _scan_interval_minutes
    _scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))

    init_db()
    # Shared dataset first (same customer book the ambiguity agent resolves
    # against); the built-in demo trio only if that file is unavailable.
    if not kyc_list.seed_from_shared_dataset():
        kyc_list.seed_defaults()

    _scheduler.add_job(
        scanner.run_scan,
        trigger="interval",
        minutes=_scan_interval_minutes,
        id="adverse_media_scan",
    )
    _scheduler.start()
    logger.info(f"Autonomous scanner started. Interval: {_scan_interval_minutes} min.")


@router.on_event("shutdown")
def shut_down():
    _scheduler.shutdown()
    logger.info("Autonomous scanner stopped.")


# ── Watchlist endpoints ───────────────────────────────────────────────────────

@router.get("/watchlist", dependencies=_DEPS, summary="List all watched entities")
def list_watchlist():
    """Returns every entity currently on the KYC scan watchlist."""
    return kyc_list.get_all()


@router.post("/watchlist", dependencies=_DEPS, summary="Add entity to watchlist")
def add_to_watchlist(entity: WatchedEntity):
    """Add a corporate entity or person to the active watchlist."""
    kyc_list.add_entity(entity)
    return {"message": f"'{entity.name}' added to watchlist."}


@router.delete("/watchlist/{name}", dependencies=_DEPS, summary="Remove entity")
def remove_from_watchlist(name: str):
    """Remove an entity from the watchlist."""
    safe_name = sanitise(name, max_length=200)
    removed   = kyc_list.remove_entity(safe_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"'{safe_name}' not found in watchlist.")
    return {"message": f"'{safe_name}' removed from watchlist."}


# ── Scan control endpoints ────────────────────────────────────────────────────

@router.post("/scan/trigger", dependencies=_DEPS, summary="Trigger scan immediately")
def trigger_scan_now():
    """Run a full scan cycle immediately in the background."""
    thread = threading.Thread(target=scanner.run_scan, daemon=True)
    thread.start()
    return {"message": "Scan cycle triggered. Check /signals/audit-log for results."}


@router.post("/scan/frequency", dependencies=_DEPS, summary="Update scan frequency")
def update_frequency(minutes: int):
    """Update the autonomous scan interval dynamically (no server restart needed)."""
    if minutes <= 0:
        raise HTTPException(status_code=400, detail="minutes must be > 0")
    _scheduler.reschedule_job("adverse_media_scan", trigger="interval", minutes=minutes)
    global _scan_interval_minutes
    _scan_interval_minutes = minutes
    logger.info(f"Scan frequency updated to {minutes} minute(s).")
    return {"message": f"Scan frequency updated to every {minutes} minute(s)."}


@router.get("/scan/status", dependencies=_DEPS, summary="Check scanner status")
def scan_status():
    """Returns scheduler status and DB statistics."""
    job = _scheduler.get_job("adverse_media_scan")
    return {
        "status"             : "running" if job else "not_running",
        "next_run"           : str(job.next_run_time) if job else None,
        "interval_minutes"   : _scan_interval_minutes,
        "articles_scanned"   : count_articles_scanned(),
        "signals_emitted"    : count_signals_emitted(),
    }


# ── Results endpoints ─────────────────────────────────────────────────────────

@router.get("/results", dependencies=_DEPS, summary="All adverse signals found")
def get_signals():
    """Returns all adverse signals ever emitted, from the database."""
    return get_all_signals()


@router.get("/results/{entity_name}", dependencies=_DEPS, summary="Signals for one entity")
def get_signals_for(entity_name: str):
    """Returns all adverse signals for a specific entity."""
    safe = sanitise(entity_name, max_length=200)
    return get_signals_for_entity(safe)


@router.get("/audit-log", dependencies=_DEPS, summary="Full audit trail")
def audit_log(limit: int = 100):
    """
    Returns the full audit trail — every decision the module made.
    Problem Statement: 'audit trail for alerts, evidence, AI decisions'.
    """
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    return get_audit_log(limit=limit)


# ── Health check (no auth needed) ────────────────────────────────────────────

@router.get("/health", summary="Health check")
def health():
    """Liveness check — no authentication required."""
    return {
        "status"  : "ok",
        "service" : "signals",
        "articles_in_db" : count_articles_scanned(),
        "signals_in_db"  : count_signals_emitted(),
    }
