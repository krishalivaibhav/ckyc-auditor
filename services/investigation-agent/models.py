from pydantic import BaseModel
from typing import List


# Input from Person 3
class RiskEvent(BaseModel):
    event_id: str
    entity_id: str
    event_type: str
    severity: str
    detected_at: str
    source_refs: List[str]


# Timeline event
class TimelineEvent(BaseModel):
    date: str
    event: str
    source_url: str
    excerpt: str


# Citation
class Citation(BaseModel):
    claim: str
    source_url: str
    excerpt: str


# Draft report
class DraftReport(BaseModel):
    summary: str
    citations: List[Citation]


# Final output to Person 5
class InvestigationOutput(BaseModel):
    entity_id: str
    timeline: List[TimelineEvent]
    draft_report: DraftReport