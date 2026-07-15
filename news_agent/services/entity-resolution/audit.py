"""Audit-log writer — schema.md §6 (append-only).

Every resolution writes one entry. The table/stream is the audit trail, so:
  - never update or delete a row;
  - never let a failing sink block the /resolve response.

Default sinks: stdout + a local append-only JSONL file. If AUDIT_URL is set,
we also POST to Person 5's backend audit endpoint (best effort).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

_AUDIT_FILE = Path(__file__).parent / "audit.log.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_audit(action: str, entity_id: str, details: dict[str, Any],
                actor: str = "agent:entity-resolution") -> dict[str, Any]:
    """Append one audit entry (schema §6). Best-effort — never raises."""
    entry = {
        "log_id": str(uuid.uuid4()),
        "actor": actor,
        "action": action,
        "entity_id": entity_id,
        "timestamp": _now_iso(),
        "details": details,
    }

    line = json.dumps(entry)
    # stdout — visible in container logs
    print(f"[AUDIT] {line}", flush=True)

    # local append-only file
    try:
        with _AUDIT_FILE.open("a") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # pragma: no cover - disk failure is non-fatal
        print(f"[AUDIT] local file write failed: {exc}", flush=True)

    # optional: forward to Person 5's backend audit endpoint
    audit_url = os.getenv("AUDIT_URL")
    if audit_url:
        try:
            httpx.post(audit_url, json=entry, timeout=3.0)
        except Exception as exc:  # pragma: no cover - remote sink is non-fatal
            print(f"[AUDIT] remote POST failed: {exc}", flush=True)

    return entry
