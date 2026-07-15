"""Local read API over the SQLite sink (`ckyc.db`) for the Flutter dashboard.

Single-device architecture: the Python agent pipeline writes `ckyc.db` (via
db/store.py); this process serves it read-only to the Flutter UI over HTTP on
127.0.0.1. It replaces the old Supabase client — same role (a data source the UI
talks to), reachable from a browser, which a local SQLite file is not.

Standard library only (http.server + sqlite3 + json): nothing to `pip install`.
It does NOT import db/store.py, whose `from contracts.models import ...` is not
satisfiable in this repo; it runs the equivalent read queries directly.

Endpoints (all GET; shapes match lib/models/models.dart exactly):
    GET /api/health
    GET /api/alerts?tier=&status=
    GET /api/entity/{client_id}
    GET /api/entity/{client_id}/timeline
    GET /api/case/{case_id}
    GET /api/case/{case_id}/sar
    GET /api/audit?object_id=
    GET /api/suppressions
    GET /api/metrics

Run:  python3 api/server.py            # serves http://127.0.0.1:8787
      python3 api/server.py --port 9000
Reseed data any time with:  python3 db/seed.py
"""
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "ckyc.db"

# Metrics have no table in schema.sql (the sink is cases/sars/audit_events only),
# so the before/after toggle is served from this configured constant. Swap for a
# real source if the pipeline ever persists it.
METRICS = {
    "baseline": {"label": "BASELINE", "alerts": 474, "precision": 0.169, "recall": 0.94},
    "ours": {"label": "OURS", "alerts": 80, "precision": 0.71, "recall": 0.90},
}

TIER_RANK = {"CRITICAL": 5, "HIGH": 4, "EDD": 3, "EDD_LITE": 2, "MONITOR": 1}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class NotFound(Exception):
    pass


# ── data access (mirrors db/store.py reads; blobs are already UI-shaped) ──────
def _case_blobs(conn) -> list[dict]:
    return [json.loads(r["data"])
            for r in conn.execute("SELECT data FROM cases ORDER BY opened_at DESC")]


def _case_blob(conn, case_id: str) -> dict:
    row = conn.execute("SELECT data FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not row:
        raise NotFound(f"case {case_id}")
    return json.loads(row["data"])


def _case_blob_for_client(conn, client_id: str) -> dict:
    row = conn.execute(
        "SELECT data FROM cases WHERE client_id=? ORDER BY opened_at DESC LIMIT 1",
        (client_id,)).fetchone()
    if not row:
        raise NotFound(f"client {client_id}")
    return json.loads(row["data"])


# ── projections: full case blob -> the slice each screen's model parses ───────
def _to_alert(c: dict) -> dict:
    a = c["assessment"]
    return {"client_id": c["client_id"], "name": c["customer"]["name"],
            "type": c["customer"].get("type", "Individual"),
            "tier": a["tier"], "status": c["status"],
            "exposure_inr": a["exposure_inr"], "case_id": c["case_id"]}


def _to_entity360(c: dict) -> dict:
    return {"customer": c["customer"], "assessment": c["assessment"],
            "candidate": c.get("candidate")}


def _to_case(c: dict) -> dict:
    return {"case_id": c["case_id"], "client_id": c["client_id"],
            "customer": c["customer"], "assessment": c["assessment"],
            "evidence": c.get("evidence", []), "sar": c.get("sar"),
            "reviewer_actions": c.get("reviewer_actions", []),
            "decision": c.get("decision")}


def _to_audit_entry(r: sqlite3.Row) -> dict:
    """audit_events row -> the AuditEntry shape the UI parses."""
    details = {"object_type": r["object_type"], "rationale": r["rationale"]}
    if r["before"] is not None:
        details["before"] = json.loads(r["before"])
    if r["after"] is not None:
        details["after"] = json.loads(r["after"])
    return {"log_id": r["audit_id"], "actor": r["actor"], "action": r["action"],
            "entity_id": r["object_id"], "timestamp": r["at"], "details": details}


# ── endpoint handlers ─────────────────────────────────────────────────────────
def alerts(conn, q) -> list[dict]:
    tier = (q.get("tier", [None])[0] or None)
    status = (q.get("status", [None])[0] or None)
    out = []
    for c in _case_blobs(conn):
        if c["status"] == "suppressed":      # suppressed matches never enter the queue
            continue
        a = _to_alert(c)
        if tier and a["tier"] != tier:
            continue
        if status and a["status"] != status:
            continue
        out.append(a)
    out.sort(key=lambda a: (TIER_RANK.get(a["tier"], 0), a["exposure_inr"]), reverse=True)
    return out


def entity360(conn, client_id) -> dict:
    return _to_entity360(_case_blob_for_client(conn, client_id))


def entity_timeline(conn, client_id) -> list[dict]:
    tl = _case_blob_for_client(conn, client_id).get("timeline", [])
    return sorted(tl, key=lambda e: e["date"])


def case(conn, case_id) -> dict:
    return _to_case(_case_blob(conn, case_id))


def case_sar(conn, case_id):
    return _case_blob(conn, case_id).get("sar")


def audit(conn, q) -> list[dict]:
    object_id = (q.get("object_id", [None])[0] or None)
    if object_id:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE object_id=? ORDER BY at DESC", (object_id,))
    else:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY at DESC")
    return [_to_audit_entry(r) for r in rows]


def suppressions(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT after FROM audit_events WHERE action='SUPPRESSED' ORDER BY at DESC")
    out = []
    for r in rows:
        if r["after"] is None:
            continue
        p = json.loads(r["after"])
        out.append({"customer": p.get("customer", ""), "matched": p.get("matched", ""),
                    "method": p.get("method", ""), "reason": p.get("reason", "")})
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "ckyc-api/1.0"

    def _send(self, code: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  # Flutter Web dev origin
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        u = urlparse(self.path)
        parts = [unquote(p) for p in u.path.strip("/").split("/") if p]
        q = parse_qs(u.query)
        try:
            conn = connect()
            try:
                payload = self._route(parts, q, conn)
            finally:
                conn.close()
            if payload is _UNHANDLED:
                return self._send(404, {"error": f"no route for /{'/'.join(parts)}"})
            self._send(200, payload)
        except NotFound as e:
            self._send(404, {"error": str(e)})
        except sqlite3.OperationalError as e:
            # Almost always: ckyc.db missing. Point the operator at the fix.
            self._send(503, {"error": f"database not ready: {e}. Run: python3 db/seed.py"})
        except Exception as e:  # noqa: BLE001 - surface as JSON, don't 500-silently
            self._send(500, {"error": repr(e)})

    def _route(self, parts, q, conn):
        # parts after the leading 'api'
        if not parts or parts[0] != "api":
            return _UNHANDLED
        p = parts[1:]
        match p:
            case ["health"]:
                return {"status": "ok"}
            case ["alerts"]:
                return alerts(conn, q)
            case ["entity", cid]:
                return entity360(conn, cid)
            case ["entity", cid, "timeline"]:
                return entity_timeline(conn, cid)
            case ["case", cid]:
                return case(conn, cid)
            case ["case", cid, "sar"]:
                return case_sar(conn, cid)
            case ["audit"]:
                return audit(conn, q)
            case ["suppressions"]:
                return suppressions(conn)
            case ["metrics"]:
                return METRICS
            case _:
                return _UNHANDLED

    def log_message(self, fmt, *args):
        print("[api] " + (fmt % args))


_UNHANDLED = object()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    if not DB.exists():
        print(f"WARNING: {DB} does not exist yet. Run `python3 db/seed.py` first.")
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"ckyc read API on http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
        httpd.shutdown()


if __name__ == "__main__":
    main()
