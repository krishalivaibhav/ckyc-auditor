"""Read-API adapter: the pipeline's SQLite sink -> the dashboard's JSON.

The agent pipeline (investigation_agent: ambiguity ER + investigation + SAR)
persists `contracts.models.Case` blobs — with the customer, assessments and
resolver candidates embedded — into its `ckyc.db`. The Flutter dashboard parses
a different, six-screen shape (lib/models/models.dart). This server is the thin
adapter between the two: it reads THAT sink and projects each persisted Case
into the JSON the Dart models already parse. No data of its own, no writes.

    pipeline service (:8001)  ->  ckyc.db  ->  THIS (:8787)  ->  Flutter

Standard library only. Endpoints (all GET):
    /api/health
    /api/alerts?tier=&status=      alert queue        (cases with tier != NONE)
    /api/entity/{client_id}        Entity 360         (customer + assessment + candidate)
    /api/entity/{client_id}/timeline
    /api/case/{case_id}            evidence three-column + SAR + reviewer actions
    /api/case/{case_id}/sar
    /api/audit?object_id=
    /api/suppressions              REJECTED candidates with their reasons
    /api/metrics                   measured eval numbers (baseline vs ours)

Run:  python3 api/server.py [--port 8787]
      CKYC_DB=/path/to/ckyc.db overrides the sink location.
"""
import argparse
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("CKYC_DB", ROOT / "investigation_agent" / "ckyc.db"))

# Measured by eval/evaluate.py in the pipeline repo (realistic cohort):
# baseline naive name screening vs the ER ladder. alerts = fp / (1 - precision).
METRICS = {
    "baseline": {"label": "BASELINE", "alerts": 474, "precision": 0.169, "recall": 0.656},
    "ours": {"label": "OURS", "alerts": 293, "precision": 0.352, "recall": 0.844},
}

TIER_RANK = {"CRITICAL": 5, "HIGH": 4, "EDD": 3, "EDD_LITE": 2, "MONITOR": 1}
_SAR_STATUS = {"DRAFT": "draft", "APPROVED": "approved", "REJECTED": "denied"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class NotFound(Exception):
    pass


# ── sink reads ────────────────────────────────────────────────────────────────
def _blobs(conn) -> list[dict]:
    return [json.loads(r["data"])
            for r in conn.execute("SELECT data FROM cases ORDER BY opened_at DESC")]


def _blob(conn, case_id: str) -> dict:
    row = conn.execute("SELECT data FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not row:
        raise NotFound(f"case {case_id}")
    return json.loads(row["data"])


def _blob_for_client(conn, client_id: str) -> dict:
    row = conn.execute(
        "SELECT data FROM cases WHERE client_id=? ORDER BY opened_at DESC LIMIT 1",
        (client_id,)).fetchone()
    if not row:
        raise NotFound(f"client {client_id}")
    return json.loads(row["data"])


# ── projections: contracts.models blob -> the six-screen shapes ──────────────
def _cust(c: dict) -> dict:
    """Embedded contracts Customer -> the UI's customer block."""
    cu = c.get("customer") or {}
    return {
        "client_id": c["client_id"],
        "name": cu.get("client_name", c["client_id"]),
        "type": "Company" if cu.get("client_type") == "Corporate" else "Individual",
        "pan": cu.get("pan"),
        "city": cu.get("branch"),
    }


def _assessment(c: dict) -> dict:
    a = (c.get("assessments") or [{}])[-1]
    cu = c.get("customer") or {}
    return {
        "tier": a.get("tier", c.get("tier", "NONE")),
        "score": a.get("score", 0.0),
        "exposure_inr": cu.get("exposure_inr", 0),
        "gates_fired": a.get("gates_fired", []),
        "suppressions": a.get("suppressions", []),
    }


def _candidate(c: dict) -> dict | None:
    """Best resolver candidate for the side-by-side: prefer CONFIRMED (the match
    the tier rests on), else the first REJECTED (so the mismatch is explainable)."""
    cands = c.get("candidates") or []
    pick = (next((x for x in cands if x["decision"] == "CONFIRMED"), None)
            or next((x for x in cands if x["decision"] == "REJECTED"), None))
    if pick is None:
        return None
    f = pick.get("features") or {}
    return {
        "candidate_id": pick.get("watchlist_id") or pick["candidate_id"],
        "matched_name": f.get("matched_on")
            or (c.get("customer") or {}).get("client_name", ""),
        "matched_pan": f.get("watchlist_pan"),
        "matched_type": _cust(c)["type"],
        "list_name": f.get("list") or pick.get("watchlist_id") or "watchlist",
        "match_method": pick.get("match_method", "?"),
        "confidence": pick.get("confidence", 0.0),
        "rejection_reason": pick.get("rejection_reason"),
    }


def _alert(c: dict) -> dict:
    cu = _cust(c)
    return {"client_id": c["client_id"], "name": cu["name"], "type": cu["type"],
            "tier": c.get("tier", "NONE"), "status": c.get("status", "OPEN").lower(),
            "exposure_inr": (c.get("customer") or {}).get("exposure_inr", 0),
            "case_id": c["case_id"]}


def _timeline(c: dict) -> list[dict]:
    out = []
    for i, t in enumerate(c.get("timeline") or []):
        out.append({
            "id": f"{c['case_id']}-t{i}",
            "client_id": c["client_id"],
            "date": t["at"],
            "event": t["summary"],
            "evidence_refs": t.get("evidence_ids", []),
            "tier_before": t.get("tier_before", "NONE"),
            "tier_after": t.get("tier_after", "NONE"),
        })
    return sorted(out, key=lambda e: e["date"])


def _evidence(c: dict) -> list[dict]:
    """Union of the assessment's evidence and the SAR's, deduped by id. The
    contract's CONFIRMED/CORRELATED/MISSING statuses ARE the three columns."""
    seen, out = set(), []
    pools = [(c.get("assessments") or [{}])[-1].get("evidence") or [],
             (c.get("sar") or {}).get("evidence") or []]
    for pool in pools:
        for e in pool:
            if e["evidence_id"] in seen:
                continue
            seen.add(e["evidence_id"])
            out.append({
                "ev_id": e["evidence_id"],
                "column": e.get("status", "CORRELATED").lower(),
                "claim": e.get("claim", ""),
                "source_name": e.get("source_name"),
                "source_url": e.get("source_url") or None,
                "excerpt": e.get("excerpt") or None,
                "confidence": e.get("confidence"),
            })
    return out


def _sar(c: dict) -> dict | None:
    s = c.get("sar")
    if not s:
        return None
    body = "\n\n".join(
        f"{k.replace('_', ' ').upper()}\n{v}" for k, v in (s.get("sections") or {}).items())
    return {"case_id": c["case_id"], "body": body,
            "citation_coverage": s.get("citation_coverage", 0.0),
            "unverified_claims": s.get("unverified_claims", []),
            "status": _SAR_STATUS.get(s.get("status", "DRAFT"), "draft")}


def _case(c: dict) -> dict:
    return {"case_id": c["case_id"], "client_id": c["client_id"],
            "customer": _cust(c), "assessment": _assessment(c),
            "evidence": _evidence(c), "sar": _sar(c),
            "reviewer_actions": [
                {"action": r.get("action", ""), "note": r.get("note", ""),
                 "reviewer": r.get("reviewer", ""), "at": r.get("at")}
                for r in c.get("reviewer_actions") or []],
            "decision": None}


def _audit_entry(r: sqlite3.Row) -> dict:
    details = {"object_type": r["object_type"], "rationale": r["rationale"]}
    if r["before"] is not None:
        details["before"] = json.loads(r["before"])
    if r["after"] is not None:
        details["after"] = json.loads(r["after"])
    return {"log_id": r["audit_id"], "actor": r["actor"], "action": r["action"],
            "entity_id": r["object_id"], "timestamp": r["at"], "details": details}


# ── endpoints ─────────────────────────────────────────────────────────────────
def alerts(conn, q) -> list[dict]:
    tier = (q.get("tier", [None])[0] or None)
    status = (q.get("status", [None])[0] or None)
    out = []
    for c in _blobs(conn):
        if c.get("tier") in (None, "NONE"):      # nothing raised -> not an alert
            continue
        a = _alert(c)
        if tier and a["tier"] != tier:
            continue
        if status and a["status"] != status:
            continue
        out.append(a)
    out.sort(key=lambda a: (TIER_RANK.get(a["tier"], 0), a["exposure_inr"]),
             reverse=True)
    return out


def entity360(conn, client_id: str) -> dict:
    c = _blob_for_client(conn, client_id)
    return {"customer": _cust(c), "assessment": _assessment(c),
            "candidate": _candidate(c)}


def audit(conn, q) -> list[dict]:
    object_id = (q.get("object_id", [None])[0] or None)
    if object_id:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE object_id=? ORDER BY at DESC",
            (object_id,))
    else:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY at DESC")
    return [_audit_entry(r) for r in rows]


def suppressions(conn) -> list[dict]:
    """The demo screen: every REJECTED candidate across the book, with its
    plain-language reason — the alerts the system refused to raise. Deduped:
    the fixture watchlist can carry an entry twice (and blocking is by index),
    which would otherwise print the same suppression twice."""
    out, seen = [], set()
    for c in _blobs(conn):
        name = _cust(c)["name"]
        for cand in c.get("candidates") or []:
            if cand.get("decision") != "REJECTED":
                continue
            f = cand.get("features") or {}
            row = {"customer": name,
                   "matched": f.get("list") or cand.get("watchlist_id") or "?",
                   "method": cand.get("match_method", "?"),
                   "reason": cand.get("rejection_reason", "")}
            key = (row["customer"], cand.get("watchlist_id"),
                   row["method"], row["reason"])
            if key not in seen:
                seen.add(key)
                out.append(row)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "ckyc-read-api/2.0"

    def _send(self, code: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
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
            self._send(503, {"error": f"pipeline sink not ready at {DB}: {e}. "
                                      "Start the pipeline service first."})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": repr(e)})

    def _route(self, parts, q, conn):
        if not parts or parts[0] != "api":
            return _UNHANDLED
        match parts[1:]:
            case ["health"]:
                return {"status": "ok", "sink": str(DB), "sink_exists": DB.exists()}
            case ["alerts"]:
                return alerts(conn, q)
            case ["entity", cid]:
                return entity360(conn, cid)
            case ["entity", cid, "timeline"]:
                return _timeline(_blob_for_client(conn, cid))
            case ["case", cid]:
                return _case(_blob(conn, cid))
            case ["case", cid, "sar"]:
                return _sar(_blob(conn, cid))
            case ["audit"]:
                return audit(conn, q)
            case ["suppressions"]:
                return suppressions(conn)
            case ["metrics"]:
                return METRICS
            case _:
                return _UNHANDLED

    def log_message(self, fmt, *args):
        print("[read-api] " + (fmt % args))


_UNHANDLED = object()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    if not DB.exists():
        print(f"WARNING: sink {DB} does not exist yet — start the pipeline "
              f"service (investigation_agent) first, or set CKYC_DB.")
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"read-api adapter on http://{args.host}:{args.port}  (sink: {DB})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
        httpd.shutdown()


if __name__ == "__main__":
    main()
