"""SQLite persistence sink for the direct pipeline.

The pipeline runs entirely in memory (see core/orchestrator.py). This module is
the ONLY thing that writes to disk, and it writes ONLY the three things that must
persist: `Case`, `SAR`, `AuditEvent`.

Design choices:
  * A `Case` is stored as one row with a JSON `data` blob = the full contract
    object PLUS the RiskAssessment(s) it embeds. The UI reconstructs everything it
    renders from that single row. (Rule 2 of the refactor explicitly permits
    intermediates to ride inside the persisted Case.)
  * The `SAR` is ALSO stored on its own so SARs can be queried directly.
  * `audit_events` is append-only, enforced by a RAISING trigger in schema.sql.
  * The DB is a demo sink: `init_db()` rebuilds it from scratch each run. DROP
    TABLE does not fire the append-only DELETE trigger, so the rebuild is legal.
"""
import json
import os
import sqlite3
from pathlib import Path

from contracts.models import AuditEvent, Case

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "schema.sql"

_TABLES = ("audit_events", "sars", "cases")   # drop order: children before parents


def db_path() -> Path:
    """Resolve the SQLite file from DATABASE_URL (sqlite:///./ckyc.db)."""
    url = os.environ.get("DATABASE_URL", "sqlite:///./ckyc.db")
    rel = url.split("sqlite:///", 1)[-1] if url.startswith("sqlite") else "./ckyc.db"
    p = Path(rel)
    return p if p.is_absolute() else (ROOT / p)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """(Re)create the schema. Idempotent: drops existing tables first. DROP TABLE
    does not trip the audit append-only trigger, so this is safe to call on boot."""
    own = conn is None
    conn = conn or connect()
    try:
        for t in _TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA.read_text())
        conn.commit()
    finally:
        if own:
            conn.close()


def persist(case: Case, assessments=None, audit: list[AuditEvent] | None = None,
            conn: sqlite3.Connection | None = None) -> None:
    """Write a Case (+ its SAR) and any AuditEvents in ONE transaction — both or
    neither. `assessments` are embedded into the stored Case JSON for the UI."""
    own = conn is None
    conn = conn or connect()
    try:
        data = case.model_dump(mode="json")
        data["assessments"] = [a.model_dump(mode="json") for a in (assessments or [])]

        with conn:   # atomic: commits on success, rolls back on any exception
            conn.execute(
                "INSERT OR REPLACE INTO cases(case_id,client_id,opened_at,status,tier,data)"
                " VALUES (?,?,?,?,?,?)",
                (case.case_id, case.client_id, data["opened_at"], case.status,
                 case.tier, json.dumps(data)))
            if case.sar:
                s = case.sar
                conn.execute(
                    "INSERT OR REPLACE INTO sars"
                    "(sar_id,case_id,drafted_at,subject_name,subject_pan,status,data)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (s.sar_id, case.case_id, s.model_dump(mode="json")["drafted_at"],
                     s.subject_name, s.subject_pan, s.status, s.model_dump_json()))
            for ev in (audit or []):
                a = ev.model_dump(mode="json")
                conn.execute(
                    "INSERT INTO audit_events"
                    "(audit_id,at,actor,action,object_type,object_id,before,after,rationale)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (a["audit_id"], a["at"], a["actor"], a["action"], a["object_type"],
                     a["object_id"],
                     json.dumps(a["before"]) if a["before"] is not None else None,
                     json.dumps(a["after"]) if a["after"] is not None else None,
                     a["rationale"]))
    finally:
        if own:
            conn.close()


# ---------------------------------------------------------------- reads (for the API)
def load_case(case_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
    """Return the stored Case JSON (with embedded assessments), or None."""
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT data FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return json.loads(row["data"]) if row else None
    finally:
        if own:
            conn.close()


def all_cases(tier: str | None = None, status: str | None = None,
              conn: sqlite3.Connection | None = None) -> list[dict]:
    own = conn is None
    conn = conn or connect()
    try:
        q, args = "SELECT data FROM cases", []
        where = []
        if tier:
            where.append("tier=?"); args.append(tier)
        if status:
            where.append("status=?"); args.append(status)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY opened_at DESC"
        return [json.loads(r["data"]) for r in conn.execute(q, args).fetchall()]
    finally:
        if own:
            conn.close()


def cases_for_client(client_id: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            "SELECT data FROM cases WHERE client_id=? ORDER BY opened_at DESC",
            (client_id,)).fetchall()
        return [json.loads(r["data"]) for r in rows]
    finally:
        if own:
            conn.close()


def audit_for(object_id: str | None = None,
              conn: sqlite3.Connection | None = None) -> list[dict]:
    own = conn is None
    conn = conn or connect()
    try:
        if object_id:
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE object_id=? ORDER BY at DESC",
                (object_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()
