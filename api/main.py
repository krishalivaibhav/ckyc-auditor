"""
FastAPI app. THIN. Each package exposes a router; this file only mounts them.

At CP0 every router serves fixtures. Each owner swaps their router's body for real
logic on their own branch, touching only their own file. That is why merges stay clean.
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

FIX = Path(__file__).resolve().parents[1] / "fixtures"
fx = lambda n: json.loads((FIX / f"{n}.json").read_text())

app = FastAPI(title="Continuous KYC Autonomous Auditor", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "mode": "fixtures"}


# ---- SAMAKSH consumes all of these. They serve fixtures until each owner wires real logic.
@app.get("/api/alerts")
def alerts(tier: str | None = None, status: str | None = None):
    cs = fx("cases")
    if tier:
        cs = [c for c in cs if c["tier"] == tier]
    if status:
        cs = [c for c in cs if c["status"] == status]
    return cs


@app.get("/api/entity/{client_id}")
def entity(client_id: str):
    cust = next((c for c in fx("customers") if c["client_id"] == client_id), None)
    asms = [a for a in fx("assessments") if a["client_id"] == client_id]
    cands = [c for c in fx("candidates") if c["client_id"] == client_id]
    return {"customer": cust, "assessments": asms, "candidates": cands}


@app.get("/api/entity/{client_id}/timeline")
def timeline(client_id: str):
    out = []
    for c in fx("cases"):
        if c["client_id"] == client_id:
            out += c["timeline"]
    return sorted(out, key=lambda e: e["at"])


@app.get("/api/case/{case_id}")
def case(case_id: str):
    return next((c for c in fx("cases") if c["case_id"] == case_id), None)


@app.get("/api/case/{case_id}/sar")
def case_sar(case_id: str):
    c = next((c for c in fx("cases") if c["case_id"] == case_id), None)
    return (c or {}).get("sar")


@app.get("/api/audit")
def audit(object_id: str | None = None):
    a = fx("audit")
    return [e for e in a if e["object_id"] == object_id] if object_id else a


@app.get("/api/suppressions")
def suppressions():
    """THE DEMO SCREEN. Alerts we did NOT raise, and why."""
    return [c for c in fx("candidates")
            if c["decision"] == "REJECTED" and c["match_method"] != "NO_MATCH"]


@app.get("/api/metrics")
def metrics():
    """Before/after. Baseline numbers are real, measured by eval/evaluate.py."""
    return {
        "baseline": {
            "stress":    {"prevalence": 0.0610, "precision": 0.452, "recall": 0.656, "fp": 97},
            "realistic": {"prevalence": 0.0020, "precision": 0.169, "recall": 0.656, "fp": 394},
        },
        "ours": {"stress": None, "realistic": None},  # VAIBHAV fills these from eval/
    }
