import uuid
from datetime import datetime
from typing import Optional

from models import Entity, ResolutionVerdict, RiskEvent, EventType, Severity
from gdelt_client import GDELTClient

# Mock URLs for downstream services (in a real scenario, these come from env vars)
INVESTIGATION_AGENT_URL = "http://investigation-agent:8004/investigate"
AUDIT_LOG_URL = "http://backend-dashboard:8005/audit"

class MediaOrchestrator:
    @staticmethod
    def process_entity(entity: Entity) -> Optional[RiskEvent]:
        """
        Queries GDELT for an entity and determines if a RiskEvent should be triggered.
        """
        articles = GDELTClient.search_adverse_media(entity.name)
        
        # Simple evaluation logic: if there is at least 1 adverse article, we trigger a risk event.
        if len(articles) > 0:
            urls = [article.get("url", "") for article in articles][:3]  # Pass top 3 URLs as evidence
            
            risk_event = RiskEvent(
                event_id=str(uuid.uuid4()),
                entity_id=entity.entity_id,
                event_type=EventType.adverse_media,
                severity=Severity.medium if len(articles) < 3 else Severity.high,
                detected_at=datetime.utcnow().isoformat() + "Z",
                source_refs=urls
            )
            
            MediaOrchestrator._notify_downstream(risk_event)
            return risk_event
            
        return None
        
    @staticmethod
    def process_verdict(verdict: ResolutionVerdict) -> Optional[RiskEvent]:
        """
        Processes a confirmed sanctions match from Person 2 and creates a RiskEvent.
        """
        if verdict.verdict == "confirmed_match":
            risk_event = RiskEvent(
                event_id=str(uuid.uuid4()),
                entity_id=verdict.query_entity_id,
                event_type=EventType.sanctions_hit,
                severity=Severity.high,
                detected_at=datetime.utcnow().isoformat() + "Z",
                source_refs=[verdict.candidate_id]
            )
            
            MediaOrchestrator._notify_downstream(risk_event)
            return risk_event
            
        return None

    @staticmethod
    def _notify_downstream(risk_event: RiskEvent):
        """
        Sends the risk event to Person 4 (Investigation Agent) and logs it.
        """
        # Note: In MVP, we just print this out instead of actually making HTTP requests
        # if the services aren't up yet to avoid crashing the poller.
        print(f"[ORCHESTRATOR] Triggering investigation for Event ID: {risk_event.event_id}")
        
        # In a full run with docker-compose, you would do:
        # requests.post(INVESTIGATION_AGENT_URL, json=risk_event.dict())
        
        # Audit Log
        print(f"[AUDIT LOG] Action 'flagged_risk_event' recorded for Entity: {risk_event.entity_id}")
