"""Tests for the verdict logic and the /resolve endpoint.

Run from the service root:  pytest
The three fixtures double as the hackathon Definition-of-Done proof points.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the service modules importable when pytest runs from the repo root.
SERVICE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from main import app  # noqa: E402
from mca import MockMCAClient  # noqa: E402
from models import ResolveRequest  # noqa: E402
from resolver import resolve_candidate  # noqa: E402

FIXTURES = SERVICE_ROOT / "fixtures"
client = TestClient(app)


def _load(name: str) -> ResolveRequest:
    return ResolveRequest(**json.loads((FIXTURES / name).read_text()))


@pytest.mark.parametrize("fixture,expected", [
    ("confirmed_match.json", "confirmed_match"),
    ("false_positive_same_name.json", "false_positive"),
    ("needs_review_no_anchor.json", "needs_review"),
])
def test_fixture_verdicts(fixture, expected):
    req = _load(fixture)
    mca = MockMCAClient()
    verdict = resolve_candidate(req.entity, req.matches.candidates[0], mca=mca)
    assert verdict.verdict == expected
    assert verdict.explanation.strip(), "explanation must be non-empty"


def test_same_name_false_positive_is_anchor_driven():
    """Flagship case: high name score but a contradicting DIN anchor must
    still produce false_positive — proving name similarity alone is beaten."""
    req = _load("false_positive_same_name.json")
    verdict = resolve_candidate(req.entity, req.matches.candidates[0], mca=MockMCAClient())
    assert verdict.verdict == "false_positive"
    assert verdict.anchor_used == "DIN"
    assert "00123456" in verdict.explanation


def test_name_only_never_confirms():
    """No anchor + a near-perfect name match must never be confirmed_match."""
    req = _load("needs_review_no_anchor.json")
    verdict = resolve_candidate(req.entity, req.matches.candidates[0], mca=MockMCAClient())
    assert verdict.verdict != "confirmed_match"
    assert verdict.anchor_used == "none"


def test_resolve_endpoint_returns_verdicts():
    req = _load("false_positive_same_name.json")
    resp = client.post("/resolve", json=req.model_dump())
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["verdict"] == "false_positive"
    assert body[0]["explanation"].strip()


def test_health():
    assert client.get("/health").json()["status"] == "ok"
