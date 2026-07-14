"""
ckyc/contracts/models.py

THE SINGLE SOURCE OF TRUTH.

Every package in this repo produces and consumes these objects and nothing else.
This file is OWNED BY VAIBHAV. Nobody else edits it. If you need a field added,
ping him — do not add it locally, do not work around it with a dict.

Frozen at Checkpoint 0. After that, changes require a team-wide sync.

Pipeline:
    Signal  --(ER)-->  Candidate  --(scoring)-->  RiskAssessment  --> Case --> SAR
    every step writes AuditEvent. every claim carries Evidence.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- enums
ListName = Literal[
    "NSE_SEBI_DEBARRED",   # regulatory debarment. HAS PAN (~81%). medium severity.
    "SABHA_PEP_CURRENT",   # sitting MP.  NO PAN. has DOB (~46%). NOT adverse.
    "SABHA_PEP_FORMER",    # former MP.   NO PAN.
    "SABHA_RCA",           # relative/close associate of an MP.
    "MHA_UAPA",            # UAPA designated terrorist/org. NO IDENTIFIERS AT ALL.
]

Tier = Literal["NONE", "MONITOR", "EDD_LITE", "EDD", "HIGH", "CRITICAL"]

MatchMethod = Literal[
    "PAN_EXACT",            # deterministic. confidence 1.0.
    "TYPE_MISMATCH_REJECT", # PAN 4th char says Company, customer is Individual -> reject
    "PAN_MISMATCH_REJECT",  # both sides have a PAN and they differ -> DIFFERENT PERSON
    "ALIAS_BARE_REJECT",    # matched only a single-token alias ('Salim') -> never alone
    "CROSS_LIST_NO_LINK",   # PEP <-> debarred share zero identifiers -> never auto-link
    "NAME_EXACT",
    "PHONETIC",             # double-metaphone. for UAPA transliterations.
    "FUZZY",
    "LLM_ADJUDICATED",
    "NO_MATCH",
]

Decision = Literal["CONFIRMED", "AMBIGUOUS", "REJECTED"]

EvidenceStatus = Literal["CONFIRMED", "CORRELATED", "MISSING"]
# ^ the PS explicitly requires separating these three. Do not collapse them.

RiskTypology = Literal[
    "FRAUD", "SANCTIONS", "TERRORISM", "CORRUPTION",
    "MARKET_MANIPULATION", "MONEY_LAUNDERING", "REGULATORY_ACTION", "NONE",
]


# ---------------------------------------------------------------- 1. inputs
class Customer(BaseModel):
    """The bank's book. Synthetic (no public dataset is a real bank's book).
    Deliberately MESSY: typos, transliterations, 'SURNAME, First', 18% missing PAN."""
    client_id: str
    client_name: str
    client_type: Literal["Individual", "Corporate"]
    pan: Optional[str] = None
    country: str = "IN"
    sector: str
    branch: str
    onboarding_date: date
    exposure_inr: int
    last_kyc_refresh: date


class WatchlistEntry(BaseModel):
    """The canonical reference side. 100% REAL. Never noisy. Owned by MOHITA."""
    watchlist_id: str                       # OpenSanctions id, e.g. NK-6yySjr...
    list: ListName
    entity_type: Literal["Individual", "Corporate", "Organization", "Unknown"]
    name: str
    aliases: list[str] = Field(default_factory=list)
    alias_quality: dict[str, Literal["full_name", "org_acronym", "bare_token"]] = Field(
        default_factory=dict
    )
    # ^ CRITICAL. 97 of 227 UAPA aliases are bare tokens ('Salim', 'Hamza', 'Amir Khan').
    #   bare_token aliases MUST NOT trigger a match on their own.
    pan: Optional[str] = None               # 4th char encodes type: P=indiv C=company H=HUF F=firm
    dob: Optional[date] = None
    party: Optional[str] = None
    status: Literal["active", "revoked", "current", "former"] = "active"
    order_id: Optional[str] = None          # co-accused clustering: 1,515 orders / 11,698 rows
    order_date: Optional[date] = None
    source_url: list[str] = Field(default_factory=list)   # real NSE circular PDFs -> citations
    first_seen: Optional[datetime] = None
    last_change: Optional[datetime] = None


# ---------------------------------------------------------------- 2. trigger
class Signal(BaseModel):
    """An atomic risk event. THE ONLY THING THAT STARTS THE PIPELINE.
    Produced by ADITYA (news) and MOHITA (watchlist deltas)."""
    signal_id: str
    signal_type: Literal["ADVERSE_MEDIA", "WATCHLIST_DELTA", "EXEC_TURNOVER"]
    occurred_at: datetime                   # when the event happened in the world
    ingested_at: datetime                   # when we saw it
    source: str                             # "GDELT" | "RSS:economictimes" | "NSE_CIRCULAR"
    source_url: str
    source_credibility: float = 0.5         # 0..1
    headline: str
    raw_excerpt: str                        # <= 300 chars. shown in the evidence panel.
    content_hash: str                       # dedup
    story_cluster_id: Optional[str] = None  # same story across outlets -> ONE alert, not five
    mentioned_names: list[str] = Field(default_factory=list)   # EXTRACTED, NOT RESOLVED
    mentioned_orgs: list[str] = Field(default_factory=list)
    risk_typology: list[RiskTypology] = Field(default_factory=list)
    severity: float = 0.0                   # 0..1
    is_rehash: bool = False                 # re-reporting of an old event


# ---------------------------------------------------------------- 3. resolution
class Candidate(BaseModel):
    """One (customer x watchlist_entry) resolution attempt. Owned by VAIBHAV.

    REJECTED candidates are NOT thrown away — they ARE the product.
    `rejection_reason` populates the suppression log, which is the headline metric."""
    candidate_id: str
    client_id: str
    watchlist_id: Optional[str] = None
    signal_id: Optional[str] = None
    match_method: MatchMethod
    confidence: float                       # 0..1
    decision: Decision
    rejection_reason: Optional[str] = None  # MANDATORY when decision == REJECTED
    features: dict = Field(default_factory=dict)   # what drove it — must be human-readable


# ---------------------------------------------------------------- 4. evidence
class Evidence(BaseModel):
    """Every factual claim anywhere in the system points at one of these.
    evidence_id is cited inline as [EV-001]. No citation -> the claim is deleted."""
    evidence_id: str                        # "EV-001"
    kind: Literal["WATCHLIST_ENTRY", "NEWS_ARTICLE", "REGISTRY_RECORD", "INTERNAL_RECORD"]
    status: EvidenceStatus                  # CONFIRMED | CORRELATED | MISSING
    claim: str                              # ONE sentence. what this proves.
    source_name: str                        # "NSE Circular NSE/INVG/75141"
    source_url: str
    excerpt: str
    retrieved_at: datetime
    confidence: float = 1.0


# ---------------------------------------------------------------- 5. scoring
class RiskAssessment(BaseModel):
    """Owned by VAIBHAV. Gates are deterministic; score is soft; tier is the output."""
    assessment_id: str
    client_id: str
    assessed_at: datetime
    prior_tier: Tier
    tier: Tier
    score: float                            # 0..1 soft score (severity x credibility x recency x ER conf)
    gates_fired: list[str] = Field(default_factory=list)
    # e.g. ["UAPA_CONFIRMED"] -> CRITICAL regardless of score. hard escalation.
    suppressions: list[str] = Field(default_factory=list)
    # e.g. ["PAN_MISMATCH:NK-6yy...", "ALIAS_BARE:Salim"] -> why we did NOT alert.
    contributing_signals: list[str] = Field(default_factory=list)
    contributing_candidates: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str = ""                   # LLM prose. EVERY claim carries [EV-nnn].


# ---------------------------------------------------------------- 6. case mgmt
class TimelineEvent(BaseModel):
    at: datetime
    kind: str                               # "SIGNAL" | "REASSESSMENT" | "REVIEW" | "SAR"
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    tier_before: Tier
    tier_after: Tier                        # tier CAN GO DOWN (revoked orders). show it.


class ReviewerAction(BaseModel):
    action_id: str
    at: datetime
    reviewer: str
    action: Literal["CONFIRM", "DISMISS", "ESCALATE", "REQUEST_INFO"]
    note: str
    # DISMISS feeds back as a suppression rule / negative example -> "continuously improve"


class SAR(BaseModel):
    """Owned by SNEHA. Structured artifact, NOT free prose."""
    sar_id: str
    case_id: str
    drafted_at: datetime
    subject_name: str
    subject_pan: Optional[str] = None
    sections: dict[str, str] = Field(default_factory=dict)
    # fixed keys: subject_identification | basis_for_suspicion | chronology_of_events
    #             | evidence_summary | risk_assessment | recommended_action
    evidence: list[Evidence] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    # ^ THE REFUSAL. things we could not source. we say so instead of inventing them.
    citation_coverage: float = 0.0          # fraction of sentences carrying >= 1 [EV-nnn]
    status: Literal["DRAFT", "APPROVED", "REJECTED"] = "DRAFT"


class Case(BaseModel):
    case_id: str
    client_id: str
    opened_at: datetime
    status: Literal["OPEN", "IN_REVIEW", "ESCALATED", "DISMISSED", "SAR_FILED"] = "OPEN"
    tier: Tier
    assessment_ids: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    sar: Optional[SAR] = None
    reviewer_actions: list[ReviewerAction] = Field(default_factory=list)


# ---------------------------------------------------------------- 7. audit
class AuditEvent(BaseModel):
    """APPEND-ONLY. Never updated, never deleted. Every agent and human writes here.
    The risk timeline and the audit trail both derive from this table."""
    audit_id: str
    at: datetime
    actor: str                              # "agent:er" | "agent:sar" | "user:analyst_1"
    action: str                             # "RESOLVED" | "SUPPRESSED" | "ESCALATED" | "DISMISSED"
    object_type: str
    object_id: str
    before: Optional[dict] = None
    after: Optional[dict] = None
    rationale: str
