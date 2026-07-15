"""
signals/router.py
-----------------
FastAPI router for the signals package.

Exposes endpoints to:
  - Add/remove entities from the KYC watchlist.
  - View the current watchlist.
  - Manually trigger a scan (useful for demo / testing).
  - Check the scan schedule status.
  - Dynamically update scan frequency.

All endpoints live under /signals/ prefix.
"""

from fastapi import APIRouter, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
from signals.models import WatchedEntity
from signals import kyc_list, scanner

router = APIRouter(prefix="/signals", tags=["Signals — Adverse Media"])

# ── Scheduler (one instance, shared across the router) ───────────────────────
_scheduler = BackgroundScheduler()
_scan_interval_minutes: int = 60


@router.on_event("startup")
def start_scheduler():
    """Start the autonomous background scan loop on app startup."""
    global _scan_interval_minutes
    import os
    _scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))

    kyc_list.seed_defaults()  # pre-load demo entities

    _scheduler.add_job(
        scanner.run_scan,
        trigger="interval",
        minutes=_scan_interval_minutes,
        id="adverse_media_scan",
    )
    _scheduler.start()
    print(f"[signals/router] Autonomous scanner started. Interval: {_scan_interval_minutes} min.")


@router.on_event("shutdown")
def stop_scheduler():
    _scheduler.shutdown()
    print("[signals/router] Autonomous scanner stopped.")


# ── Watchlist endpoints ───────────────────────────────────────────────────────

@router.get("/watchlist", summary="List all watched entities")
def list_watchlist():
    """Returns every entity currently in the KYC scan watchlist."""
    return kyc_list.get_all()


@router.post("/watchlist", summary="Add an entity to the watchlist")
def add_to_watchlist(entity: WatchedEntity):
    """Add a corporate entity or person to the active KYC watchlist."""
    kyc_list.add_entity(entity)
    return {"message": f"'{entity.name}' added to watchlist."}


@router.delete("/watchlist/{name}", summary="Remove an entity from the watchlist")
def remove_from_watchlist(name: str):
    """Remove an entity from the active KYC watchlist by name."""
    removed = kyc_list.remove_entity(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"'{name}' not found in watchlist.")
    return {"message": f"'{name}' removed from watchlist."}


# ── Control endpoints ─────────────────────────────────────────────────────────

@router.post("/scan/trigger", summary="Manually trigger a full scan cycle")
def trigger_scan_now():
    """
    Runs a full scan cycle immediately, without waiting for the next scheduled run.
    Useful for demos and testing.
    """
    import threading
    thread = threading.Thread(target=scanner.run_scan, daemon=True)
    thread.start()
    return {"message": "Scan cycle triggered. Check server logs for results."}


@router.post("/scan/frequency", summary="Dynamically update scan frequency")
def update_frequency(minutes: int):
    """
    Update how often the autonomous scanner runs, without restarting the server.
    Example: minutes=1440 for daily, minutes=10080 for weekly.
    """
    if minutes <= 0:
        raise HTTPException(status_code=400, detail="minutes must be > 0")
    _scheduler.reschedule_job("adverse_media_scan", trigger="interval", minutes=minutes)
    global _scan_interval_minutes
    _scan_interval_minutes = minutes
    return {"message": f"Scan frequency updated to every {minutes} minute(s)."}


@router.get("/scan/status", summary="Check scanner status")
def scan_status():
    """Returns the current schedule status of the autonomous scanner."""
    job = _scheduler.get_job("adverse_media_scan")
    if not job:
        return {"status": "not_running"}
    return {
        "status": "running",
        "next_run": str(job.next_run_time),
        "interval_minutes": _scan_interval_minutes,
    }
