"""
FastAPI app. THIN. It runs the in-memory pipeline (core/orchestrator) and serves
the PERSISTED `Case` objects the UI renders.

There is no database between pipeline stages — the DB is a sink. On startup the app
rebuilds the SQLite sink and seeds it by running every fixture customer through
`run_pipeline()`, so the case/alert endpoints have real, pipeline-produced Cases to
return (not raw fixture tables). `/api/suppressions` and `/api/metrics` are the ER
demo/pitch endpoints and read from the resolver output and the eval numbers.
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.ingest import (find_customers, news_signal_to_contract,
                        sanctions_trigger_to_contract)
from contracts.models import Customer, WatchlistEntry
from core.blocking import Blocker
from core.orchestrator import load_watchlist, run_pipeline, seed_from_fixtures
from core.verify import verify_hit
from db.store import all_cases, audit_for, cases_for_client, load_case

FIX = Path(__file__).resolve().parents[1] / "fixtures"
fx = lambda n: json.loads((FIX / f"{n}.json").read_text())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: rebuild the SQLite sink and seed it by running the pipeline on
    every fixture customer, so the case/alert endpoints have real Cases to serve."""
    seed_from_fixtures()
    yield


app = FastAPI(title="Continuous KYC Autonomous Auditor", version="0.2.0",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "mode": "pipeline+sqlite"}


# ---- Cases the UI renders — served from the PERSISTED sink, produced by the pipeline.
@app.get("/api/alerts")
def alerts(tier: str | None = None, status: str | None = None):
    return all_cases(tier=tier, status=status)


@app.get("/api/entity/{client_id}")
def entity(client_id: str):
    """The persisted Case(s) for a client, with the assessments embedded in each."""
    cases = cases_for_client(client_id)
    if not cases:
        raise HTTPException(404, f"no persisted case for {client_id}")
    return {"client_id": client_id, "cases": cases}


@app.get("/api/entity/{client_id}/timeline")
def timeline(client_id: str):
    out = []
    for c in cases_for_client(client_id):
        out += c.get("timeline", [])
    return sorted(out, key=lambda e: e["at"])


@app.get("/api/case/{case_id}")
def case(case_id: str):
    c = load_case(case_id)
    if c is None:
        raise HTTPException(404, f"no case {case_id}")
    return c


@app.get("/api/case/{case_id}/sar")
def case_sar(case_id: str):
    c = load_case(case_id)
    return (c or {}).get("sar")


@app.get("/api/audit")
def audit(object_id: str | None = None):
    return audit_for(object_id)


# ---- Live demo: run the pipeline for one fixture customer on demand.
@app.post("/api/pipeline/{client_id}")
def pipeline(client_id: str):
    cust = next((c for c in fx("customers") if c["client_id"] == client_id), None)
    if cust is None:
        raise HTTPException(404, f"no fixture customer {client_id}")
    # Interactive run: use_llm=True — live Anthropic adjudication for CRITICAL/EDD/
    # AMBIGUOUS cases when a key is set. (Startup seeding uses the deterministic path.)
    return run_pipeline(Customer(**cust), use_llm=True).model_dump(mode="json")


# ---- Near-real-time ingest: the two producer agents push events here. --------

def _parse_customer(raw: dict) -> Customer:
    try:
        return Customer(**raw)
    except Exception as e:  # noqa: BLE001 — bad hit shape -> 422, not a 500
        raise HTTPException(422, f"invalid customer in payload: {e}")


def _case_summary(case) -> dict:
    return {"case_id": case.case_id, "client_id": case.client_id,
            "status": case.status, "tier": case.tier,
            "sar_drafted": case.sar is not None,
            "timeline_events": len(case.timeline)}


@app.post("/api/verify")
def verify(payload: dict = Body(...)):
    """Verification only (no case opened): run a hit through the ER ladder and
    return the verdict. The sanctions monitor's --verify-only mode uses this."""
    if "customer" not in payload:
        raise HTTPException(400, "payload must include a 'customer' object")
    customer = _parse_customer(payload["customer"])
    cand_dicts = payload.get("candidates")
    if cand_dicts:
        try:
            entries = [WatchlistEntry(**c) for c in cand_dicts]
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"invalid candidate in payload: {e}")
    else:
        entries = Blocker(load_watchlist()).candidates(
            customer.client_name, customer.pan)
    return verify_hit(customer, entries)


@app.post("/api/ingest")
def ingest_sanctions_hit(payload: dict = Body(...)):
    """A sanctions hit: {customer, candidates, trigger}. Verify through the ER
    ladder, then run the FULL pipeline (assess -> investigate -> SAR -> persist)
    with the hit's watchlist entries and the triggering delta as a Signal."""
    if "customer" not in payload:
        raise HTTPException(400, "payload must include a 'customer' object")
    customer = _parse_customer(payload["customer"])
    try:
        entries = [WatchlistEntry(**c) for c in payload.get("candidates") or []]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"invalid candidate in payload: {e}")

    verdict = verify_hit(customer, entries) if entries else None
    sig = (sanctions_trigger_to_contract(payload["trigger"])
           if payload.get("trigger") else None)
    case = run_pipeline(customer, use_llm=True,
                        external_signals=[sig] if sig else None,
                        extra_watchlist=entries or None)
    return {"verdict": (verdict or {}).get("verdict"),
            "suppressions": (verdict or {}).get("suppressions", []),
            "case": _case_summary(case)}


@app.post("/signals/ingest")
def ingest_news_signal(payload: dict = Body(...)):
    """The news agent's emitter POSTs its own Signal JSON here (name-only, its
    own lineage — see api/ingest.py). Resolve entity_name against the customer
    book; every matching customer gets a full pipeline run with the adverse-media
    Signal attached. No match is a 200, not an error: the emitter must never
    retry-loop on names outside the book."""
    name = payload.get("entity_name", "")
    if not name:
        raise HTTPException(400, "payload must include entity_name")
    matches = find_customers(name)
    if not matches:
        return {"matched": False, "entity_name": name,
                "detail": "no customer in the book with this name; signal ignored"}
    sig = news_signal_to_contract(payload)
    cases = [run_pipeline(cust, use_llm=True, external_signals=[sig])
             for cust in matches]
    return {"matched": True, "entity_name": name,
            "customers": [c.client_id for c in matches],
            "cases": [_case_summary(c) for c in cases]}


# ---- Judges' demo: the scripted two-phase Vijay Mallya scenario (test mode).
# The read-API forwards here when the dashboard toggles live -> test. Runs the
# real agent functions against a SEPARATE demo sink (ckyc_demo.db) and narrates
# the flow to this terminal. See api/demo.py.
from api import demo as _demo  # noqa: E402 — grouped with its routes on purpose


@app.post("/demo/start")
def demo_start():
    return _demo.start()


@app.post("/demo/timeskip")
def demo_timeskip():
    try:
        return _demo.timeskip()
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.get("/demo/status")
def demo_status():
    return _demo.status()


# ---- ER demo/pitch endpoints (unchanged contract).
@app.get("/api/suppressions")
def suppressions():
    """THE DEMO SCREEN. Alerts we did NOT raise, and why. The REJECTED candidates
    with their rejection_reason are the product."""
    return [c for c in fx("candidates")
            if c["decision"] == "REJECTED" and c["match_method"] != "NO_MATCH"]


@app.get("/api/metrics")
def metrics():
    """Before/after, both real and measured by eval/evaluate.py."""
    return {
        "baseline": {
            "stress":    {"prevalence": 0.0610, "precision": 0.452, "recall": 0.656, "fp": 97},
            "realistic": {"prevalence": 0.0020, "precision": 0.169, "recall": 0.656, "fp": 394},
        },
        "ours": {
            "stress":    {"prevalence": 0.0610, "precision": 0.632, "recall": 0.844, "fp": 60},
            "realistic": {"prevalence": 0.0020, "precision": 0.352, "recall": 0.844, "fp": 190},
        },
    }
