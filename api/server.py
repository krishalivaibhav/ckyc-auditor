"""Read-API adapter: the pipeline's SQLite sink -> the dashboard's JSON.

The agent pipeline (investigation_agent: ambiguity ER + investigation + SAR)
persists `contracts.models.Case` blobs — with the customer, assessments and
resolver candidates embedded — into its `ckyc.db`. The Flutter dashboard parses
a different, six-screen shape (lib/models/models.dart). This server is the thin
adapter between the two: it reads THAT sink and projects each persisted Case
into the JSON the Dart models already parse. No data of its own, no writes.

    pipeline service (:8001)  ->  ckyc.db  ->  THIS (:8787)  ->  Flutter

Standard library only (the SAR-to-PDF route shells out to the Chrome/Chromium
binary the demo already requires for `flutter run -d chrome` — no pip deps).
Endpoints (all GET):
    /api/health
    /api/alerts?tier=&status=      alert queue        (cases with tier != NONE)
    /api/entity/{client_id}        Entity 360         (customer + assessment + candidate)
    /api/entity/{client_id}/timeline
    /api/entity/{client_id}/case   the case for a client (no case_id needed)
    /api/entity/{client_id}/sar/pdf  the SAR rendered into casefile_sar_exact_template.html, as a PDF download
    /api/entity/{client_id}/sar/html the same rendered SAR, served inline for preview (not an attachment)
    /api/case/{case_id}            evidence three-column + SAR + reviewer actions
    /api/case/{case_id}/sar
    /api/audit?object_id=
    /api/suppressions              REJECTED candidates with their reasons
    /api/reports                   cases that carry a drafted SAR (the Reports tab)
    /api/metrics                   measured eval numbers (baseline vs ours)

Writes (POST, JSON body) — the reviewer's terminal decision, straight to the sink:
    /api/case/{case_id}/review       {action: BLACKLIST|DISMISS|ESCALATE, note?, reviewer}
    /api/case/{case_id}/sar/review   {action: APPROVE|DENY, note?, reviewer}

Risk-alert email (Gmail SMTP; recipient set in the Settings screen):
    GET  /api/alert-config           {email, smtp_configured}
    POST /api/alert-config           {email}  — set the alert recipient
    POST /api/alert-config/test      send a test alert to the recipient
  A HIGH/CRITICAL hit (the demo's +15-month time skip) emails the recipient.

Live/test mode — the judges' demo (see investigation_agent/api/demo.py):
    GET  /api/mode                   {mode, phase}
    POST /api/mode                   {mode: live|test} — test (re)runs the scripted
                                     scenario and re-points ALL reads at ckyc_demo.db
    POST /api/demo/timeskip          advance the test scenario +15 months

Run:  python3 api/server.py [--port 8787]
      CKYC_DB=/path/to/ckyc.db overrides the sink location.
      CHROME_BIN=/path/to/chrome overrides the PDF-render browser.
"""
import argparse
import json
import os
import re
import shutil
import smtplib
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Minimal stdlib `.env` loader (the read-api runs on system python3, not the
    pipeline venv, so python-dotenv isn't available). Only sets keys that aren't
    already in the environment, so a real env var always wins."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()
# The live sink is the pipeline's own DB — investigation_agent runs with that
# folder as its CWD, so db/store.py materialises `ckyc.db` in there. The retired
# db/seed.py wrote a stand-in at the repo root; prefer the pipeline sink when it
# exists so the dashboard shows real investigation output, not the stale seed.
# CKYC_DB overrides everything.
_PIPELINE_SINK = ROOT / "investigation_agent" / "ckyc.db"
DB = (Path(os.environ["CKYC_DB"]) if os.environ.get("CKYC_DB")
      else _PIPELINE_SINK if _PIPELINE_SINK.exists()
      else ROOT / "ckyc.db")

# ── live/test mode ────────────────────────────────────────────────────────────
# LIVE serves the pipeline's real sink (DB above). TEST serves the scripted demo
# scenario's own sink, produced by the pipeline service's /demo endpoints (see
# investigation_agent/api/demo.py). Toggling to test triggers the scenario run —
# the backend terminal narrates the agent flow while this API re-points reads.
DEMO_DB = Path(os.environ.get("CKYC_DEMO_DB",
                              ROOT / "investigation_agent" / "ckyc_demo.db"))
PIPELINE_URL = os.environ.get("PIPELINE_URL", "http://127.0.0.1:8001")
_MODE = "live"    # "live" | "test"
_PHASE = 0        # 0 = not started, 1 = first news, 2 = after the time skip


def current_db() -> Path:
    return DEMO_DB if _MODE == "test" else DB


def _pipeline_post(path: str, timeout: float = 180.0) -> dict:
    """Forward a demo trigger to the pipeline service (it owns the agents and
    the narration). stdlib-only, like the rest of this server."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"{PIPELINE_URL}{path}", data=b"{}",
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"pipeline service unreachable at {PIPELINE_URL}{path}: {e}. "
            "Is the pipeline running? (./run_backend.sh starts it)")

# ── Gmail alert emails ────────────────────────────────────────────────────────
# When a HIGH/CRITICAL entity is hit (in the demo, that's the +15-month time skip
# escalating Vijay Mallya EDD -> CRITICAL), email the compliance recipient the
# reviewer configured in the Settings screen. Sender credentials come from .env
# (ALERT_SMTP_USER / ALERT_SMTP_PASS); the recipient is persisted here.
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
ALERT_TIERS = {"HIGH", "CRITICAL"}
ALERT_CONFIG_FILE = ROOT / "api" / ".alert_config.json"


def _load_alert_email() -> str | None:
    try:
        return json.loads(ALERT_CONFIG_FILE.read_text()).get("email") or None
    except (OSError, ValueError):
        return None


_ALERT_EMAIL = _load_alert_email()


def _smtp_creds() -> tuple[str | None, str | None]:
    user = os.environ.get("ALERT_SMTP_USER") or None
    # Gmail shows app passwords with spaces; they work without them.
    pw = (os.environ.get("ALERT_SMTP_PASS") or "").replace(" ", "") or None
    return user, pw


def _smtp_configured() -> bool:
    user, pw = _smtp_creds()
    return bool(user and pw)


def send_alert_email(recipient: str, *, name: str, tier: str, client_id: str,
                     case_id: str, exposure_inr: float | int | None = None,
                     test: bool = False) -> None:
    """Send one alert via Gmail SMTP (SSL). Raises on any failure so the caller
    can report why the send didn't happen."""
    user, pw = _smtp_creds()
    if not (user and pw):
        raise RuntimeError(
            "SMTP not configured — set ALERT_SMTP_USER/ALERT_SMTP_PASS in .env")
    if not recipient:
        raise RuntimeError("no alert recipient configured")

    exposure = ""
    if exposure_inr:
        cr = float(exposure_inr) / 1e7
        exposure = f"\nExposure at risk : ₹{cr:,.2f} Cr"
    subject = (f"[TechMKYC] {'TEST — ' if test else ''}{tier} risk alert — {name}")
    body = (
        f"{'This is a TEST alert from the TechMKYC dashboard.' if test else ''}\n"
        f"A {tier} risk entity has been flagged by the continuous-KYC pipeline.\n\n"
        f"Entity           : {name}\n"
        f"Client ID        : {client_id}\n"
        f"Risk tier        : {tier}\n"
        f"Case             : {case_id}{exposure}\n\n"
        "Open the dashboard alert queue to review the case, evidence and SAR "
        "draft.\n\n— TechMKYC Autonomous Compliance System"
    ).lstrip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(body)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.login(user, pw)
        smtp.send_message(msg)


def _maybe_alert_on_timeskip(result: dict) -> dict | None:
    """Called after the demo time skip. If it escalated to HIGH/CRITICAL and a
    recipient is configured, email the alert. Never raises — the time skip must
    still succeed even if the mail server is unreachable; the outcome is returned
    for the UI to surface."""
    tier = str(result.get("tier", "")).upper()
    if tier not in ALERT_TIERS:
        return None
    if not _ALERT_EMAIL:
        return {"sent": False, "reason": "no recipient configured in Settings"}
    case_id = result.get("case_id", "")
    name, client_id, exposure = case_id, "", None
    try:                                   # enrich from the demo sink if we can
        conn = connect()
        try:
            blob = _blob(conn, case_id)
            cust = _cust(blob)
            name = cust["name"]
            client_id = blob.get("client_id", "")
            exposure = _assessment(blob)["exposure_inr"]
        finally:
            conn.close()
    except Exception:                      # noqa: BLE001 — best-effort enrichment
        pass
    try:
        send_alert_email(_ALERT_EMAIL, name=name, tier=tier, client_id=client_id,
                         case_id=case_id, exposure_inr=exposure)
        return {"sent": True, "to": _ALERT_EMAIL, "tier": tier}
    except Exception as e:                 # noqa: BLE001
        return {"sent": False, "error": str(e), "to": _ALERT_EMAIL}


# Measured by eval/evaluate.py in the pipeline repo (realistic cohort):
# baseline naive name screening vs the ER ladder. alerts = fp / (1 - precision).
METRICS = {
    "baseline": {"label": "BASELINE", "alerts": 474, "precision": 0.169, "recall": 0.656},
    "ours": {"label": "OURS", "alerts": 293, "precision": 0.352, "recall": 0.844},
}

TIER_RANK = {"CRITICAL": 5, "HIGH": 4, "EDD": 3, "EDD_LITE": 2, "MONITOR": 1}
_SAR_STATUS = {"DRAFT": "draft", "APPROVED": "approved", "REJECTED": "denied"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{current_db()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class NotFound(Exception):
    pass


class BadRequest(Exception):
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
    """Embedded Customer -> the UI's customer block. Tolerates two blob shapes:
    the seed/db writes the final UI shape ({name,type,pan,city}); the live
    pipeline writes the contracts shape ({client_name,client_type,branch})."""
    cu = c.get("customer") or {}
    ctype = cu.get("type") or (
        "Company" if cu.get("client_type") == "Corporate" else "Individual")
    return {
        "client_id": cu.get("client_id", c["client_id"]),
        "name": cu.get("name") or cu.get("client_name") or c["client_id"],
        "type": ctype,
        "pan": cu.get("pan"),
        "city": cu.get("city") or cu.get("branch"),
    }


def _assessment(c: dict) -> dict:
    # Final shape carries a singular `assessment`; the pipeline carries
    # `assessments[]` (take the latest) with exposure on the customer.
    a = c.get("assessment") or (c.get("assessments") or [{}])[-1]
    cu = c.get("customer") or {}
    return {
        "tier": a.get("tier", c.get("tier", "NONE")),
        "score": a.get("score", 0.0),
        "exposure_inr": a.get("exposure_inr", cu.get("exposure_inr", 0)),
        "gates_fired": a.get("gates_fired", []),
        "suppressions": a.get("suppressions", []),
    }


def _candidate(c: dict) -> dict | None:
    """Best resolver candidate for the side-by-side: prefer CONFIRMED (the match
    the tier rests on), else the first REJECTED (so the mismatch is explainable).
    Final-shape blobs already carry the single projected `candidate` (or null)."""
    if "candidate" in c:
        return c["candidate"]
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
        # Rejects carry the entry's PAN as watchlist_pan; a PAN_EXACT confirm
        # records pan_match+customer_pan (the two are equal by definition).
        "matched_pan": f.get("watchlist_pan")
            or (f.get("customer_pan") if f.get("pan_match") else None),
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
            "exposure_inr": _assessment(c)["exposure_inr"],
            "case_id": c["case_id"]}


def _timeline(c: dict) -> list[dict]:
    out = []
    for i, t in enumerate(c.get("timeline") or []):
        out.append({
            "id": t.get("id", f"{c['case_id']}-t{i}"),
            "client_id": t.get("client_id", c["client_id"]),
            "date": t.get("date") or t.get("at"),
            "event": t.get("event") or t.get("summary", ""),
            "evidence_refs": t.get("evidence_refs") or t.get("evidence_ids", []),
            "tier_before": t.get("tier_before", "NONE"),
            "tier_after": t.get("tier_after", "NONE"),
        })
    return sorted(out, key=lambda e: e["date"])


def _evidence(c: dict) -> list[dict]:
    """The three evidence columns (CONFIRMED/CORRELATED/MISSING). Final-shape
    blobs carry a top-level `evidence[]` already in column form; the pipeline
    carries evidence inside the assessment and SAR, keyed `evidence_id`/`status`."""
    fin = c.get("evidence")
    if fin is not None:
        pools = [fin]
    else:
        pools = [(c.get("assessments") or [{}])[-1].get("evidence") or [],
                 (c.get("sar") or {}).get("evidence") or []]
    seen, out = set(), []
    for pool in pools:
        for e in pool:
            ev_id = e.get("ev_id") or e.get("evidence_id")
            if ev_id in seen:
                continue
            seen.add(ev_id)
            out.append({
                "ev_id": ev_id,
                "column": (e.get("column") or e.get("status", "correlated")).lower(),
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
    # Final shape has a ready `body`; the pipeline emits titled `sections`.
    body = s.get("body")
    if body is None:
        body = "\n\n".join(
            f"{k.replace('_', ' ').upper()}\n{v}"
            for k, v in (s.get("sections") or {}).items())
    return {"case_id": c["case_id"], "body": body,
            "citation_coverage": s.get("citation_coverage", 0.0),
            "unverified_claims": s.get("unverified_claims", []),
            "status": _SAR_STATUS.get(str(s.get("status", "DRAFT")).upper(), "draft")}


# ── SAR -> filled PDF (casefile_sar_exact_template.html) ──────────────────────
SAR_TEMPLATE = ROOT / "casefile_sar_exact_template.html"


def _esc(v) -> str:
    if v is None:
        return ""
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _fmt_dt(iso: str | None) -> tuple[str, str]:
    if not iso:
        return "", ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso), ""
    return dt.strftime("%d %b %Y"), dt.strftime("%H:%M")


def _sar_template_fields(c: dict) -> dict[str, str]:
    """Map a persisted Case blob -> casefile_sar_exact_template.html placeholders.

    Every value here is either pipeline output or left blank — nothing is
    invented for fields the pipeline doesn't produce (phone numbers, the
    human `received_by` sign-off): those render as empty fill-boxes for a
    reviewer to complete by hand, same as the paper form would."""
    sar = c.get("sar") or {}
    sections = sar.get("sections") or {}
    cust = _cust(c)
    date_str, time_str = _fmt_dt(sar.get("drafted_at") or c.get("opened_at"))
    affiliation = cust["type"] + (f" · {cust['city']}" if cust.get("city") else "")
    return {
        "incident_date": date_str,
        "incident_time": time_str,
        "incident_location": cust.get("city") or "",
        "sections.basis_for_suspicion": sections.get("basis_for_suspicion", ""),
        "subject_name": cust.get("name", ""),
        "subject_affiliation": affiliation,
        "subject_phone": "",
        "sections.subject_identification": sections.get("subject_identification", ""),
        "reporting_party_name": "TechMKYC Autonomous Compliance System",
        "reporting_party_agency": "Continuous KYC Auditor — Investigation Agent",
        "reporting_party_phone": "",
        "received_by": "",
        "received_datetime": "",
        "forwarded_datetime": "",
    }


def _find_browser() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and shutil.which(env):
        return shutil.which(env)
    for name in ("google-chrome-stable", "google-chrome", "chromium-browser",
                 "chromium", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def render_sar_html(c: dict) -> str:
    """Fill casefile_sar_exact_template.html with this case's SAR. Shared by the
    PDF route (printed to PDF) and the inline preview route (served as HTML)."""
    if not c.get("sar"):
        raise NotFound(f"no SAR drafted for case {c['case_id']}")
    html = SAR_TEMPLATE.read_text(encoding="utf-8")
    for key, val in _sar_template_fields(c).items():
        html = html.replace("{{" + key + "}}", _esc(val))
    return html


def render_sar_pdf(c: dict) -> tuple[bytes, str]:
    """Fill the template with this case's SAR, then print it to PDF via a
    headless browser (the same Chrome `flutter run -d chrome` already needs —
    no extra pip dependency for PDF rendering)."""
    html = render_sar_html(c)

    browser = _find_browser()
    if not browser:
        raise RuntimeError(
            "No Chrome/Chromium binary found to render the PDF. Install "
            "google-chrome or chromium (or set CHROME_BIN) — the same "
            "browser `flutter run -d chrome` uses.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="sar_"))
    try:
        html_path = tmp_dir / "sar.html"
        pdf_path = tmp_dir / "sar.pdf"
        html_path.write_text(html, encoding="utf-8")
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
               f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
               "--no-pdf-header-footer", html_path.as_uri()]
        proc = subprocess.run(cmd, capture_output=True, timeout=25)
        if proc.returncode != 0 or not pdf_path.exists():
            raise RuntimeError("PDF render failed: "
                                f"{proc.stderr.decode(errors='replace')[:500]}")
        data = pdf_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", _cust(c)["name"] or c["client_id"])
    return data, f"SAR_{safe_name}_{c['case_id']}.pdf"


def _case(c: dict) -> dict:
    return {"case_id": c["case_id"], "client_id": c["client_id"],
            "customer": _cust(c), "assessment": _assessment(c),
            "evidence": _evidence(c), "sar": _sar(c),
            "reviewer_actions": [
                {"action": r.get("action", ""), "note": r.get("note", ""),
                 "reviewer": r.get("reviewer", ""), "at": r.get("at")}
                for r in c.get("reviewer_actions") or []],
            "decision": c.get("decision")}


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
        st = c.get("status", "").lower()
        if st == "suppressed":                   # refused by the system -> not an alert
            continue
        # A reviewer's terminal calls also leave the ACTIVE queue: a dismissed
        # false positive is resolved; a blacklisted entity stays (it's escalated
        # for filing, status ESCALATED, so it never hits this branch).
        if st == "dismissed" or c.get("decision") == "dismissed":
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


def reports(conn) -> list[dict]:
    """Reports tab: every case that carries a drafted SAR, projected to just the
    card fields (name/tier/status/coverage). The dashboard previews / downloads
    each via the /api/entity/{cid}/sar routes."""
    out = []
    for c in _blobs(conn):
        s = _sar(c)
        if not s:
            continue
        cu = _cust(c)
        out.append({
            "client_id": c["client_id"], "case_id": c["case_id"],
            "name": cu["name"], "type": cu["type"],
            "tier": c.get("tier", "NONE"),
            "sar_status": s["status"],
            "citation_coverage": s["citation_coverage"],
        })
    out.sort(key=lambda r: TIER_RANK.get(r["tier"], 0), reverse=True)
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
    plain-language reason — the alerts the system refused to raise. Deduped.

    Primary source is the append-only audit trail: SUPPRESSED events carry the
    projected {customer,matched,method,reason} in their `after` payload (see the
    schema comment listing SUPPRESSED as a first-class action). Falls back to
    REJECTED resolver candidates on blobs for the live-pipeline shape."""
    out, seen = [], set()

    def _add(row):
        key = (row["customer"], row["matched"], row["method"], row["reason"])
        if key not in seen:
            seen.add(key)
            out.append(row)

    for r in conn.execute(
            "SELECT after FROM audit_events WHERE action='SUPPRESSED' ORDER BY at DESC"):
        if not r["after"]:
            continue
        a = json.loads(r["after"])
        _add({"customer": a.get("customer", "?"), "matched": a.get("matched", "?"),
              "method": a.get("method", "?"), "reason": a.get("reason", "")})

    for c in _blobs(conn):
        name = _cust(c)["name"]
        for cand in c.get("candidates") or []:
            if cand.get("decision") != "REJECTED":
                continue
            f = cand.get("features") or {}
            _add({"customer": name,
                  "matched": f.get("list") or cand.get("watchlist_id") or "?",
                  "method": cand.get("match_method", "?"),
                  "reason": cand.get("rejection_reason", "")})
    return out


# ── writes: reviewer decisions (the ONE mutation path) ───────────────────────
# The dashboard is read-only except for the human reviewer's terminal decision.
# These write straight to the SAME sink the pipeline persists to, honouring the
# append-only audit trail: UPDATE the Case (status + JSON blob), keep the SAR
# row's status in sync, and INSERT exactly one audit_events row — all atomically.
# The append-only triggers forbid UPDATE/DELETE on audit_events; we only INSERT.
_ENTITY_ACTIONS = {   # action -> (case.decision | None keeps prior, case.status, audit action)
    "BLACKLIST": ("blacklisted", "ESCALATED", "CASE_BLACKLISTED"),
    "DISMISS": ("dismissed", "DISMISSED", "CASE_DISMISSED"),
    # Escalate is NOT terminal: leave `decision` untouched so the case stays in
    # the queue and a senior reviewer can still blacklist/dismiss it.
    "ESCALATE": (None, "ESCALATED", "CASE_ESCALATED"),
}
_SAR_REVIEW = {       # action -> (sar.status, case.status | None = keep, audit action)
    "APPROVE": ("APPROVED", "ESCALATED", "SAR_APPROVED"),
    "DENY": ("REJECTED", None, "SAR_REJECTED"),
}


def connect_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{current_db()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(conn, actor, action, object_type, object_id, before, after,
                  rationale):
    conn.execute(
        "INSERT INTO audit_events"
        "(audit_id,at,actor,action,object_type,object_id,before,after,rationale)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), _now_iso(), actor, action, object_type, object_id,
         json.dumps(before) if before is not None else None,
         json.dumps(after) if after is not None else None, rationale))


def review_case(case_id: str, action: str, note: str, reviewer: str) -> dict:
    """Reviewer's terminal decision on the entity (blacklist / dismiss)."""
    action = (action or "").upper()
    if action not in _ENTITY_ACTIONS:
        raise BadRequest(f"unknown case action {action!r}")
    decision, new_status, audit_action = _ENTITY_ACTIONS[action]
    conn = connect_rw()
    try:
        row = conn.execute("SELECT data, status FROM cases WHERE case_id=?",
                           (case_id,)).fetchone()
        if not row:
            raise NotFound(f"case {case_id}")
        blob = json.loads(row["data"])
        before = {"status": row["status"], "decision": blob.get("decision")}
        if decision is not None:      # escalate keeps the prior decision
            blob["decision"] = decision
        blob["status"] = new_status
        blob.setdefault("reviewer_actions", []).append(
            {"action": action, "note": note, "reviewer": reviewer, "at": _now_iso()})
        after = {"status": new_status, "decision": blob.get("decision")}
        with conn:
            conn.execute("UPDATE cases SET status=?, data=? WHERE case_id=?",
                         (new_status, json.dumps(blob), case_id))
            _append_audit(conn, f"human:{reviewer}", audit_action, "Case", case_id,
                          before, after, note or f"{decision} by {reviewer}")
        return {"ok": True, "case_id": case_id, "decision": decision,
                "status": new_status}
    finally:
        conn.close()


def review_sar(case_id: str, action: str, note: str, reviewer: str) -> dict:
    """Reviewer's decision on the drafted SAR (approve / deny)."""
    action = (action or "").upper()
    if action not in _SAR_REVIEW:
        raise BadRequest(f"unknown SAR action {action!r}")
    sar_status, case_status, audit_action = _SAR_REVIEW[action]
    conn = connect_rw()
    try:
        row = conn.execute("SELECT data, status FROM cases WHERE case_id=?",
                           (case_id,)).fetchone()
        if not row:
            raise NotFound(f"case {case_id}")
        blob = json.loads(row["data"])
        sar = blob.get("sar")
        if not sar:
            raise NotFound(f"no SAR drafted for case {case_id}")
        before = {"sar_status": sar.get("status"), "status": row["status"]}
        sar["status"] = sar_status
        new_case_status = case_status or row["status"]
        blob["status"] = new_case_status
        blob.setdefault("reviewer_actions", []).append(
            {"action": action, "note": note, "reviewer": reviewer, "at": _now_iso()})
        after = {"sar_status": sar_status, "status": new_case_status}
        with conn:
            conn.execute("UPDATE cases SET status=?, data=? WHERE case_id=?",
                         (new_case_status, json.dumps(blob), case_id))
            # Keep the standalone sars row's status column honest (UI reads the
            # Case blob, but the queryable table shouldn't drift).
            conn.execute("UPDATE sars SET status=? WHERE case_id=?",
                         (sar_status, case_id))
            _append_audit(conn, f"human:{reviewer}", audit_action, "SAR", case_id,
                          before, after, note or f"SAR {sar_status.lower()} by {reviewer}")
        return {"ok": True, "case_id": case_id, "sar_status": sar_status,
                "status": new_case_status}
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "ckyc-read-api/2.0"

    def _send(self, code: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_pdf(self, data: bytes, filename: str):
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            raise BadRequest(f"invalid JSON body: {e}")
        if not isinstance(body, dict):
            raise BadRequest("JSON body must be an object")
        return body

    def do_POST(self):
        u = urlparse(self.path)
        parts = [unquote(p) for p in u.path.strip("/").split("/") if p]
        try:
            body = self._read_json()
            result = self._route_post(parts, body)
            if result is _UNHANDLED:
                return self._send(404,
                                  {"error": f"no route for POST /{'/'.join(parts)}"})
            self._send(200, result)
        except BadRequest as e:
            self._send(400, {"error": str(e)})
        except NotFound as e:
            self._send(404, {"error": str(e)})
        except sqlite3.OperationalError as e:
            self._send(503, {"error": f"sink not writable at {current_db()}: {e}"})
        except RuntimeError as e:   # pipeline unreachable etc.
            self._send(502, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": repr(e)})

    def _route_post(self, parts, body):
        global _MODE, _PHASE
        # /api/mode                         switch live <-> test (test runs the scenario)
        # /api/demo/timeskip                advance the test scenario +15 months
        # /api/case/{case_id}/review        entity blacklist / dismiss
        # /api/case/{case_id}/sar/review    SAR approve / deny
        if parts == ["api", "mode"]:
            mode = str(body.get("mode") or "").lower()
            if mode not in ("live", "test"):
                raise BadRequest(f"mode must be 'live' or 'test', got {mode!r}")
            if mode == "test":
                # (Re)start the scripted scenario — the pipeline terminal
                # narrates the agent flow; we re-point reads at the demo sink.
                result = _pipeline_post("/demo/start")
                _MODE, _PHASE = "test", int(result.get("phase", 1))
            else:
                _MODE, _PHASE = "live", 0
            return {"mode": _MODE, "phase": _PHASE}

        if parts == ["api", "demo", "timeskip"]:
            if _MODE != "test":
                raise BadRequest("time skip only works in test mode")
            result = _pipeline_post("/demo/timeskip")
            _PHASE = int(result.get("phase", 2))
            alert = _maybe_alert_on_timeskip(result)
            return {"mode": _MODE, "phase": _PHASE,
                    **({"alert": alert} if alert else {})}

        # /api/alert-config          set the risk-alert recipient email
        # /api/alert-config/test     send a test alert to verify wiring
        if parts[:2] == ["api", "alert-config"]:
            return self._route_alert_config(parts[2:], body)

        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "case":
            reviewer = str(body.get("reviewer") or "unknown")
            note = str(body.get("note") or "")
            match parts[2:]:
                case [cid, "review"]:
                    return review_case(cid, body.get("action"), note, reviewer)
                case [cid, "sar", "review"]:
                    return review_sar(cid, body.get("action"), note, reviewer)
        return _UNHANDLED

    def _route_alert_config(self, sub, body):
        global _ALERT_EMAIL
        email = str(body.get("email") or _ALERT_EMAIL or "").strip()
        if sub == ["test"]:               # POST /api/alert-config/test
            if not email:
                raise BadRequest("no recipient — save an alert email first")
            send_alert_email(email, name="Test Entity", tier="CRITICAL",
                             client_id="TEST-0000", case_id="CASE-TEST",
                             exposure_inr=None, test=True)
            return {"ok": True, "sent": True, "to": email}
        if sub == []:                     # POST /api/alert-config
            if not email or "@" not in email:
                raise BadRequest(f"invalid email {email!r}")
            _ALERT_EMAIL = email
            try:
                ALERT_CONFIG_FILE.write_text(json.dumps({"email": email}))
            except OSError as e:
                raise RuntimeError(f"could not persist alert config: {e}")
            return {"email": _ALERT_EMAIL, "smtp_configured": _smtp_configured()}
        return _UNHANDLED

    def do_GET(self):
        u = urlparse(self.path)
        parts = [unquote(p) for p in u.path.strip("/").split("/") if p]
        q = parse_qs(u.query)
        try:
            # The PDF/HTML SAR routes return bytes/markup, not JSON — handled
            # outside _route.
            if len(parts) == 5 and parts[0] == "api" and parts[1] == "entity" \
                    and parts[3] == "sar" and parts[4] in ("pdf", "html"):
                conn = connect()
                try:
                    blob = _blob_for_client(conn, parts[2])
                finally:
                    conn.close()
                if parts[4] == "html":
                    return self._send_html(render_sar_html(blob))
                data, filename = render_sar_pdf(blob)
                return self._send_pdf(data, filename)

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
        except RuntimeError as e:
            self._send(500, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": repr(e)})

    def _route(self, parts, q, conn):
        if not parts or parts[0] != "api":
            return _UNHANDLED
        match parts[1:]:
            case ["health"]:
                db = current_db()
                return {"status": "ok", "mode": _MODE, "sink": str(db),
                        "sink_exists": db.exists()}
            case ["mode"]:
                return {"mode": _MODE, "phase": _PHASE}
            case ["alert-config"]:
                return {"email": _ALERT_EMAIL,
                        "smtp_configured": _smtp_configured()}
            case ["alerts"]:
                return alerts(conn, q)
            case ["entity", cid]:
                return entity360(conn, cid)
            case ["entity", cid, "timeline"]:
                return _timeline(_blob_for_client(conn, cid))
            case ["entity", cid, "case"]:
                # The case (evidence + SAR) for a client, without needing to know
                # its case_id — the detail screen has only the client_id.
                return _case(_blob_for_client(conn, cid))
            case ["case", cid]:
                return _case(_blob(conn, cid))
            case ["case", cid, "sar"]:
                return _sar(_blob(conn, cid))
            case ["audit"]:
                return audit(conn, q)
            case ["suppressions"]:
                return suppressions(conn)
            case ["reports"]:
                return reports(conn)
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
