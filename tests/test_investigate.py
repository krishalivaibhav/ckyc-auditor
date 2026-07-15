"""Investigation-agent tests. Prove the two properties the brief demands:
the agent corroborates an AMBIGUOUS/CRITICAL match, and it CAN conclude
INSUFFICIENT_EVIDENCE (return only MISSING evidence) instead of inventing a finding.
Runs fully offline — no ANTHROPIC_API_KEY required (deterministic adjudicator).
"""
import json
from pathlib import Path

from contracts.models import Evidence, RiskAssessment
from core.investigate import investigate

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _assessment(aid):
    return next(RiskAssessment(**a)
                for a in json.loads((FIX / "assessments.json").read_text())
                if a["assessment_id"] == aid)


def test_investigate_ambiguous_fixture_corroborates_without_confirming():
    # ASM-003 is the CRITICAL UAPA case whose contributing candidate CAND-007 the
    # resolver left AMBIGUOUS (PHONETIC). No identifier exists, so the best the
    # agent can honestly reach is CORRELATED — never a hard CONFIRMED.
    ev = investigate(_assessment("ASM-003"))
    assert ev and all(isinstance(e, Evidence) for e in ev)
    statuses = {e.status for e in ev}
    assert "CORRELATED" in statuses          # designating authority (NIA) named in the article
    assert "MISSING" in statuses             # ...but no identifier to confirm identity
    assert "CONFIRMED" not in statuses       # UAPA carries no identifier — cannot confirm
    # the three statuses are never collapsed into one
    assert statuses <= {"CONFIRMED", "CORRELATED", "MISSING"}


def test_investigate_can_return_insufficient_evidence():
    # A UAPA name-only hit whose triggering signal corroborates nothing: no
    # authority named, no identifier, no shared order. The agent must return ONLY
    # MISSING evidence (INSUFFICIENT_EVIDENCE) rather than manufacture a finding.
    bland = RiskAssessment(
        assessment_id="ASM-INSUF", client_id="C999",
        assessed_at="2026-07-11T09:00:00+00:00", prior_tier="NONE", tier="CRITICAL",
        score=0.0, contributing_signals=["SIG-Z"], contributing_candidates=["CAND-Z"],
        explanation="name-only UAPA hit, no corroborating context")
    sources = {
        "signals": [{"signal_id": "SIG-Z", "headline": "Local cricket league wraps up",
                     "raw_excerpt": "A community sports roundup.", "mentioned_orgs": []}],
        "candidates": [{"candidate_id": "CAND-Z", "watchlist_id": "W-Z",
                        "match_method": "PHONETIC", "decision": "AMBIGUOUS", "features": {}}],
        "watchlist": [{"watchlist_id": "W-Z", "list": "MHA_UAPA", "name": "Salim",
                       "aliases": [], "pan": None, "order_id": None, "dob": None,
                       "source_url": []}],
    }
    ev = investigate(bland, sources=sources)
    assert ev, "must still emit the MISSING evidence it looked for"
    assert {e.status for e in ev} == {"MISSING"}          # nothing corroborated
    assert all(e.confidence == 0.0 for e in ev)           # low-confidence only


def test_reasoning_step_is_pluggable():
    # The reasoning step (Anthropic by default) is injectable; its verdict/findings
    # flow through to typed Evidence. This exercises the seam without a network call.
    def fake_adjudicate(ctx):
        return {"verdict": "CONFIRMED",
                "findings": [{"status": "CONFIRMED", "claim": "identifier matched",
                              "source_name": "test", "source_url": "", "excerpt": "",
                              "confidence": 1.0, "kind": "WATCHLIST_ENTRY"}]}
    ev = investigate(_assessment("ASM-003"), adjudicate=fake_adjudicate)
    assert len(ev) == 1 and ev[0].status == "CONFIRMED" and ev[0].confidence == 1.0
