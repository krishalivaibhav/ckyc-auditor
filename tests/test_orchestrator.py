"""Pipeline + persistence-sink tests. Proves the refactor invariants:
end-to-end run on fixtures, typed hand-offs, only Case/SAR/AuditEvent persist,
audit append-only enforced.
"""
import os
import sqlite3
import tempfile

# Point the sink at a throwaway DB before importing the store.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/ckyc_test.db"

import pytest

from contracts.models import Case
from contracts.models import Customer
from core.orchestrator import _fx, run_pipeline, seed_from_fixtures
from db import store


def test_pipeline_produces_typed_case():
    cust = Customer(**_fx("customers")[0])
    case = run_pipeline(cust, persist_result=False)
    assert isinstance(case, Case)                 # typed hand-off, not a dict
    assert case.client_id == cust.client_id
    assert case.tier in ("NONE", "MONITOR", "EDD_LITE", "EDD", "HIGH", "CRITICAL")


def test_seed_runs_end_to_end_on_fixtures():
    cases = seed_from_fixtures()
    assert len(cases) == 10
    got = store.load_case("CASE-C1001")
    assert got is not None and got["tier"] == "HIGH"
    # intermediate RiskAssessment rides embedded inside the Case, not a standalone table
    assert got["assessments"] and got["assessments"][0]["client_id"] == "C1001"


def test_only_case_sar_audit_persist():
    seed_from_fixtures()
    conn = store.connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert tables == {"cases", "sars", "audit_events"}


def _customer(client_id):
    return Customer(**next(c for c in _fx("customers") if c["client_id"] == client_id))


def test_pan_exact_high_skips_investigation(monkeypatch):
    """A deterministic HIGH (PAN-exact, confidence 1.0) is already settled — the
    orchestrator must NOT spend an investigation on it. draft_sar still runs."""
    import core.orchestrator as orch
    calls = {"investigate": 0}
    monkeypatch.setattr(orch, "investigate",
                        lambda a: calls.__setitem__("investigate", calls["investigate"] + 1) or [])

    case = orch.run_pipeline(_customer("C1001"), persist_result=False)   # PAN-exact -> HIGH
    assert case.tier == "HIGH"
    assert calls["investigate"] == 0        # investigation skipped
    assert case.sar is not None             # draft_sar still ran


def test_critical_still_investigates(monkeypatch):
    """CRITICAL (UAPA) is a contextual tier — investigation must run."""
    import core.orchestrator as orch
    calls = {"investigate": 0}
    monkeypatch.setattr(orch, "investigate",
                        lambda a: calls.__setitem__("investigate", calls["investigate"] + 1) or [])

    case = orch.run_pipeline(_customer("C1007"), persist_result=False)   # UAPA -> CRITICAL
    assert case.tier == "CRITICAL"
    assert calls["investigate"] == 1        # investigation ran


def test_audit_is_append_only():
    seed_from_fixtures()
    conn = store.connect()
    aid = conn.execute("SELECT audit_id FROM audit_events LIMIT 1").fetchone()[0]
    with pytest.raises(sqlite3.Error):            # RAISE(FAIL) fails loudly
        conn.execute("UPDATE audit_events SET rationale='x' WHERE audit_id=?", (aid,))
        conn.commit()
    with pytest.raises(sqlite3.Error):
        conn.execute("DELETE FROM audit_events WHERE audit_id=?", (aid,))
        conn.commit()
    conn.close()
