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
