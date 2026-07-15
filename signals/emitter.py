"""
signals/emitter.py
------------------
Emits confirmed adverse signals to the downstream system (core/ orchestrator).

In the full system, this does a POST to the core/ API's /signals endpoint.
For standalone demo mode, it prints to stdout and saves to a local JSON log.
"""

import json
import os
import httpx
from datetime import datetime, timezone
from .models import Signal

# Where to send confirmed signals. This will be the core/ orchestrator's endpoint.
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000/signals/ingest")

# Local log file for demo purposes
LOG_FILE = "signals_log.jsonl"


def emit(signal: Signal):
    """
    Sends a confirmed adverse Signal downstream.

    1. Writes to local JSON log (always — audit trail).
    2. POSTs to the core/ orchestrator API (if available).
    """
    payload = signal.model_dump()

    # ── Step 1: Write to local audit log ────────────────────────────────────
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

    print(
        f"\n🚨 [Emitter] ADVERSE SIGNAL EMITTED\n"
        f"   Entity  : {signal.entity_name}\n"
        f"   Severity: {signal.severity.value.upper()}\n"
        f"   Confidence: {signal.confidence:.0%}\n"
        f"   Headline: {signal.headline}\n"
        f"   Reason  : {signal.triage_reasoning}\n"
        f"   URL     : {signal.url}\n"
    )

    # ── Step 2: POST to core/ API ────────────────────────────────────────────
    try:
        response = httpx.post(CORE_API_URL, json=payload, timeout=5)
        if response.status_code in (200, 201):
            print(f"[Emitter] Signal accepted by core/ API.")
        else:
            print(f"[Emitter] core/ API returned {response.status_code}. Will retry next cycle.")
    except httpx.RequestError:
        # Core is not up yet (e.g. demo mode) — that's fine, we already logged it locally
        print(f"[Emitter] core/ API unreachable. Signal saved to '{LOG_FILE}' for pickup.")
