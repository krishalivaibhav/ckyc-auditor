"""Every fixture must validate against contracts/models.py. If this fails, main is broken."""
import json
from pathlib import Path

import pytest
from contracts.models import (AuditEvent, Candidate, Case, Customer, RiskAssessment,
                              SAR, Signal, WatchlistEntry)

FIX = Path(__file__).resolve().parents[1] / "fixtures"

CASES = [(Customer, "customers"), (WatchlistEntry, "watchlist"), (Signal, "signals"),
         (Candidate, "candidates"), (RiskAssessment, "assessments"), (Case, "cases"),
         (SAR, "sar"), (AuditEvent, "audit")]


@pytest.mark.parametrize("model,name", CASES)
def test_fixture_validates(model, name):
    rows = json.loads((FIX / f"{name}.json").read_text())
    assert rows, f"{name}.json is empty"
    for r in rows:
        model(**r)


def test_rejected_candidate_must_carry_a_reason():
    """A REJECTED candidate without a reason silently loses a false-positive suppression.
    The suppression log IS the product. This must never regress."""
    for c in json.loads((FIX / "candidates.json").read_text()):
        if c["decision"] == "REJECTED":
            assert c["rejection_reason"], f"{c['candidate_id']} rejected with no reason"


def test_evidence_status_is_never_collapsed():
    """The PS explicitly requires separating confirmed / correlated / missing."""
    seen = {e["status"] for a in json.loads((FIX / "assessments.json").read_text())
            for e in a["evidence"]}
    assert {"CONFIRMED", "CORRELATED", "MISSING"} <= seen


def test_a_tier_can_go_down():
    """De-escalation. A revoked SEBI order must lower risk. Almost nobody builds this."""
    tl = [e for c in json.loads((FIX / "cases.json").read_text()) for e in c["timeline"]]
    order = ["NONE", "MONITOR", "EDD_LITE", "EDD", "HIGH", "CRITICAL"]
    assert any(order.index(e["tier_after"]) < order.index(e["tier_before"]) for e in tl)
