import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
import httpx
from src.schemas import Entity, Candidate, CandidateMatches
from src.config import settings
from src.db import AuditLogger
from src.services.opensanctions import OpenSanctionsClient
from src.services.scoring import ScoringEngine
from src.dependencies import get_db_client, get_opensanctions_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sanctions-agent")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Events
    logger.info("Starting up TechMKYC Sanctions Agent...")
    logger.info(f"Connecting database logger to: {settings.DATABASE_URL}")
    app.state.db_client = AuditLogger(settings.DATABASE_URL)
    
    logger.info("Initializing OpenSanctions API client...")
    app.state.opensanctions_client = OpenSanctionsClient(settings.OPENSANCTIONS_API_KEY)
    
    yield
    # Shutdown Events
    logger.info("Shutting down TechMKYC Sanctions Agent...")

app = FastAPI(
    title="TechMKYC Sanctions/PEP Data Agent",
    description="Person 1: Screen corporate entities against sanctions lists",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health")
def health_check():
    """Service health check endpoint."""
    return {"status": "healthy"}

@app.post("/screen", response_model=CandidateMatches)
async def screen_entity(
    entity: Entity,
    db: AuditLogger = Depends(get_db_client),
    opensanctions: OpenSanctionsClient = Depends(get_opensanctions_client)
):
    """
    Screen an entity against sanctions and PEP watchlists.
    Queries upstream API, applies local fuzzy similarity scoring, logs to append-only database,
    and returns a ranked list of potential matches.
    """
    logger.info(f"Received screening request for entity_id={entity.entity_id}, type={entity.type}, name='{entity.name}'")

    # 1. Query OpenSanctions API
    try:
        logger.info(f"Querying OpenSanctions for match candidates...")
        raw_candidates = await opensanctions.match_entity(entity)
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenSanctions API returned HTTP error (status {e.response.status_code}): {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Upstream database error: OpenSanctions returned HTTP status {e.response.status_code}"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to OpenSanctions API: {e}")
        raise HTTPException(
            status_code=503,
            detail="Upstream database unavailable: Connection failed"
        )
    except Exception as e:
        logger.error(f"Unexpected error querying OpenSanctions client: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal service error: {str(e)}"
        )

    # 2. Score matches locally using ScoringEngine
    processed_candidates = []
    logger.info(f"Retrieved {len(raw_candidates)} matching candidates. Running similarity scoring...")
    
    for raw_cand in raw_candidates:
        raw_data = raw_cand.get("raw", {})
        
        # Calculate local fuzzy score on names
        local_name_score = ScoringEngine.compute_name_score(entity, raw_data)
        
        # Identify matched attributes (name, DOB, nationality)
        matched_fields = ScoringEngine.identify_matched_fields(entity, raw_data)
        
        # Merge local name score with API confidence score
        api_score = raw_cand.get("score", 0.0)
        final_score = ScoringEngine.merge_scores(local_name_score, api_score)

        processed_candidates.append(Candidate(
            candidate_id=raw_cand.get("candidate_id", ""),
            matched_name=raw_cand.get("matched_name", ""),
            score=final_score,
            source_list=raw_cand.get("source_list", "Watchlist"),
            matched_fields=matched_fields,
            raw=raw_data
        ))

    # Sort candidate matches by score descending
    processed_candidates.sort(key=lambda c: c.score, reverse=True)

    # 3. Write event to Audit Trail (exactly once, and wrapped to never crash api response)
    outcome_summary = {
        "candidate_count": len(processed_candidates),
        "top_match_score": processed_candidates[0].score if processed_candidates else 0.0,
        "matched_fields": list(set([f for c in processed_candidates for f in c.matched_fields]))
    }

    try:
        logger.info(f"Writing audit log entry for entity_id={entity.entity_id}...")
        await db.log_screening(str(entity.entity_id), outcome_summary)
    except Exception as log_err:
        logger.error(f"Fail-safe audit logging triggered by unhandled exception: {log_err}")

    logger.info(f"Screening complete. Returning {len(processed_candidates)} ranked candidates for entity_id={entity.entity_id}")

    return CandidateMatches(
        query_entity_id=entity.entity_id,
        candidates=processed_candidates
    )


