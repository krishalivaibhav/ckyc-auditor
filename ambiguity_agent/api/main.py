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
    return run_pipeline(Customer(**cust)).model_dump(mode="json")


# ---- The connection point: verify a hit sent by the sanctions agent.
@app.post("/api/verify")
def verify(payload: dict = Body(...)):
    """Take a sanctions-agent hit and run it through the ER ladder for verification.

    Body: {"customer": <Customer>, "candidates": [<WatchlistEntry>, ...]}
    `candidates` are the watchlist entries the sanctions agent already matched (the
    hit). If omitted, we block against our own watchlist and verify what surfaces.
    Returns the verdict (CONFIRMED / SUPPRESSED / AMBIGUOUS / NO_MATCH) with every
    rejection carrying a plain-language reason.
    """
    if "customer" not in payload:
        raise HTTPException(400, "payload must include a 'customer' object")
    try:
        customer = Customer(**payload["customer"])
    except Exception as e:  # noqa: BLE001 — bad hit shape → 422, not a 500
        raise HTTPException(422, f"invalid customer in hit: {e}")

    cand_dicts = payload.get("candidates")
    if cand_dicts:
        try:
            entries = [WatchlistEntry(**c) for c in cand_dicts]
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"invalid candidate in hit: {e}")
    else:
        # No pre-screened candidates → block against our own watchlist.
        entries = Blocker(load_watchlist()).candidates(
            customer.client_name, customer.pan)

    return verify_hit(customer, entries)


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
