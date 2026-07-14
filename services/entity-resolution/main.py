"""FastAPI interface for the Entity Resolution & Scoring service (Person 2).

    POST /resolve  — candidates + entity → one ResolutionVerdict per candidate
    GET  /health   — liveness probe

Every verdict is written to the audit log with action "resolved_verdict".
"""

from __future__ import annotations

from fastapi import FastAPI

from audit import write_audit
from mca import get_mca_client
from models import ResolutionVerdict, ResolveRequest
from resolver import resolve_candidate

app = FastAPI(
    title="TechMKYC — Entity Resolution & Scoring",
    description="Turns candidate sanction/PEP matches into explainable "
                "verdicts, anchored on MCA DIN/CIN government-verified data.",
    version="0.1.0",
)


@app.get("/")
def root() -> dict[str, object]:
    """Landing route — points to the interactive docs and endpoints."""
    return {
        "service": "entity-resolution",
        "description": "Turns candidate sanction/PEP matches into explainable "
                       "verdicts, anchored on MCA DIN/CIN government-verified data.",
        "docs": "/docs",
        "endpoints": {"resolve": "POST /resolve", "health": "GET /health"},
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "entity-resolution"}


@app.post("/resolve", response_model=list[ResolutionVerdict])
def resolve(request: ResolveRequest) -> list[ResolutionVerdict]:
    """Resolve every candidate for the given entity into a verdict."""
    mca = get_mca_client()
    verdicts: list[ResolutionVerdict] = []

    for candidate in request.matches.candidates:
        verdict = resolve_candidate(request.entity, candidate, mca=mca)
        verdicts.append(verdict)

        write_audit(
            action="resolved_verdict",
            entity_id=request.entity.entity_id,
            details={
                "candidate_id": verdict.candidate_id,
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "anchor_used": verdict.anchor_used,
                "source_list": candidate.source_list,
                "explanation": verdict.explanation,
            },
        )

    return verdicts
