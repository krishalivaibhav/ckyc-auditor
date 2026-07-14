"""Pydantic models — the single source of shape truth for this service.

These mirror docs/schema.md §1 (Entity), §2 (CandidateMatches) and §3
(ResolutionVerdict) EXACTLY. Do not rename fields — schema.md is the frozen
team contract. If a field must change, announce it in the team chat first.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── schema.md §1 — Entity (input) ────────────────────────────────────────────
class Entity(BaseModel):
    entity_id: str
    type: Literal["person", "company"]
    name: str
    aliases: list[str] = Field(default_factory=list)
    dob: str | None = None                # YYYY-MM-DD | null
    nationality: str | None = None        # ISO-3166 alpha-2 | null
    din_or_cin: str | None = None         # the government anchor
    source: Literal["internal_kyc", "client_input"] = "internal_kyc"


# ── schema.md §2 — Candidate matches (Person 1 output → our input) ────────────
class Candidate(BaseModel):
    candidate_id: str
    matched_name: str
    score: float = 0.0
    source_list: str = ""                 # OFAC | UN | EU | PEP | ...
    matched_fields: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CandidateMatches(BaseModel):
    query_entity_id: str
    candidates: list[Candidate] = Field(default_factory=list)


# ── Our request envelope: candidates + the original entity to check against ───
class ResolveRequest(BaseModel):
    entity: Entity
    matches: CandidateMatches


# ── schema.md §3 — Resolution verdict (our output → Person 3, Person 5) ───────
Verdict = Literal["confirmed_match", "false_positive", "needs_review"]
AnchorUsed = Literal["DIN", "CIN", "none"]


class ResolutionVerdict(BaseModel):
    query_entity_id: str
    candidate_id: str
    verdict: Verdict
    confidence: float = 0.0
    explanation: str                      # non-empty, human-readable (enforced)
    anchor_used: AnchorUsed = "none"
    resolved_at: str                      # ISO 8601 UTC
