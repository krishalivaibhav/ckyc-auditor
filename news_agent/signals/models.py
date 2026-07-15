"""
signals/models.py
-----------------
Strict data contracts for the adverse media signals module.
All inputs and outputs are validated by Pydantic — nothing enters or
leaves this module without being checked against these schemas.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


# ── Enumerations ─────────────────────────────────────────────────────────────

class Severity(str, Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"

class EntityType(str, Enum):
    company = "company"
    person  = "person"

class MatchVerdict(str, Enum):
    confirmed    = "confirmed"      # article is definitely about our entity
    false_positive = "false_positive"  # same name, different entity
    needs_review = "needs_review"   # LLM not confident enough — send to human

class SignalStatus(str, Enum):
    raw      = "raw"         # just fetched from news API
    triaged  = "triaged"     # AI has assessed it
    emitted  = "emitted"     # sent downstream to core/
    rejected = "rejected"    # confirmed false positive


# ── Watchlist Entry ───────────────────────────────────────────────────────────

class WatchedEntity(BaseModel):
    """A corporate entity or person on the KYC watchlist to be monitored."""
    entity_id:   str        = Field(default_factory=lambda: str(uuid.uuid4()))
    name:        str        = Field(..., min_length=2, max_length=200)
    aliases:     list[str]  = Field(default=[])
    entity_type: EntityType = EntityType.company
    country:     str        = "IN"   # ISO country code — default India
    sector:      Optional[str] = None
    notes:       Optional[str] = None
    added_at:    str        = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Entity name cannot be blank or whitespace.")
        return v.strip()


# ── Raw Article (straight from NewsAPI) ───────────────────────────────────────

class RawArticle(BaseModel):
    """Represents a single news article fetched from NewsAPI, before any AI analysis."""
    article_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name:  str
    headline:     str
    description:  str = ""
    url:          str
    source_name:  str
    published_at: str
    fetched_at:   str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    content_hash: str = ""   # SHA-256 of headline+url — used for deduplication


# ── Entity Resolution Result ──────────────────────────────────────────────────

class EntityResolution(BaseModel):
    """
    Result of the entity-resolution step (Problem Statement: 'separate a corporate
    director from an unrelated person with the same name').
    """
    article_id:   str
    entity_name:  str
    verdict:      MatchVerdict
    confidence:   float = Field(ge=0.0, le=1.0)
    evidence:     str   # plain-English: which fields matched or did not match
    resolved_at:  str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Confirmed Adverse Signal ──────────────────────────────────────────────────

class Signal(BaseModel):
    """
    A confirmed adverse news signal emitted downstream after passing both
    entity-resolution and semantic-triage checks.
    """
    signal_id:        str      = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name:      str
    headline:         str
    url:              str
    source_name:      str
    published_at:     str
    detected_at:      str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    severity:         Severity
    confidence:       float = Field(ge=0.0, le=1.0)
    triage_reasoning: str          # AI explanation of why this is adverse
    er_reasoning:     str          # Entity-resolution reasoning
    status:           SignalStatus = SignalStatus.emitted


# ── Audit Event ───────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    """
    Append-only record of every decision made by the module.
    Problem Statement: 'audit trail for alerts, evidence, AI decisions'.
    """
    event_id:     str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:    str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entity_name:  str
    article_id:   Optional[str] = None
    signal_id:    Optional[str] = None
    action:       str   # e.g. "FETCHED", "DEDUPLICATED", "ER_CONFIRMED", "TRIAGED_ADVERSE"
    detail:       str   # plain-English description of what happened
    confidence:   Optional[float] = None
