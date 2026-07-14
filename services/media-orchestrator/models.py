from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class EntityType(str, Enum):
    person = "person"
    company = "company"

class EntitySource(str, Enum):
    internal_kyc = "internal_kyc"
    client_input = "client_input"

class Entity(BaseModel):
    entity_id: str
    type: EntityType
    name: str
    aliases: List[str]
    dob: Optional[str] = None
    nationality: Optional[str] = None
    din_or_cin: Optional[str] = None
    source: EntitySource

class VerdictType(str, Enum):
    confirmed_match = "confirmed_match"
    false_positive = "false_positive"
    needs_review = "needs_review"

class ResolutionVerdict(BaseModel):
    query_entity_id: str
    candidate_id: str
    verdict: VerdictType
    confidence: float
    explanation: str
    anchor_used: str
    resolved_at: str

class EventType(str, Enum):
    sanctions_hit = "sanctions_hit"
    adverse_media = "adverse_media"
    ownership_change = "ownership_change"

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RiskEvent(BaseModel):
    event_id: str
    entity_id: str
    event_type: EventType
    severity: Severity
    detected_at: str
    source_refs: List[str]

class AuditLog(BaseModel):
    log_id: str
    actor: str
    action: str
    entity_id: str
    timestamp: str
    details: dict
