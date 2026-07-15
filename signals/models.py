"""
signals/models.py
-----------------
Local data models for the signals package.
These will be replaced by contracts/models.py once Vaibhav merges CP0.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Signal(BaseModel):
    """
    A confirmed adverse news signal about a watched entity.
    Produced by: signals/triage_agent.py
    Consumed by: core (entity resolution + risk scoring)
    """
    entity_name: str           # name from the KYC watchlist
    headline: str              # article headline
    url: str                   # source URL
    source: str                # e.g. "NewsAPI", "GDELT"
    published_at: str          # ISO 8601 timestamp of the article
    detected_at: str           # ISO 8601 timestamp when WE found it
    severity: Severity         # low / medium / high
    triage_reasoning: str      # plain-English explanation from the LLM why this is adverse
    confidence: float          # 0.0 to 1.0 — how confident the LLM is that this is adverse


class WatchedEntity(BaseModel):
    """
    A corporate entity or person we are monitoring from the KYC list.
    """
    name: str
    aliases: list[str] = []    # alternate names to search (e.g. "Infy" for "Infosys")
    entity_type: str = "company"  # "company" or "person"
    notes: Optional[str] = None
