from fastapi import FastAPI, BackgroundTasks, HTTPException
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import uuid

from models import Entity, ResolutionVerdict, RiskEvent
from orchestrator import MediaOrchestrator

# Global mock list of tracked entities for the continuous poller
TRACKED_ENTITIES = [
    Entity(
        entity_id=str(uuid.uuid4()),
        type="company",
        name="Mock Corp Inc",
        aliases=[],
        source="internal_kyc"
    )
]

scheduler = BackgroundScheduler()

def poll_gdelt():
    """
    Background job that continuously polls for adverse media on tracked entities.
    """
    print("[POLLER] Running scheduled adverse media check...")
    for entity in TRACKED_ENTITIES:
        print(f"[POLLER] Checking entity: {entity.name}")
        MediaOrchestrator.process_entity(entity)

import os

# Read the polling frequency from environment variables (default to 15 minutes if not set)
# For quarterly scans, you might set this to roughly 129600 minutes (90 days)
SCAN_FREQUENCY_MINUTES = int(os.getenv("SCAN_FREQUENCY_MINUTES", "15"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler on startup with the configured frequency
    scheduler.add_job(poll_gdelt, "interval", minutes=SCAN_FREQUENCY_MINUTES, id="gdelt_poll_job")
    scheduler.start()
    print(f"Background poller started. Scanning every {SCAN_FREQUENCY_MINUTES} minutes.")
    yield
    # Shutdown the scheduler on exit
    scheduler.shutdown()
    print("Background poller stopped.")

app = FastAPI(title="Media Orchestrator", lifespan=lifespan)

@app.post("/trigger-check", response_model=RiskEvent)
async def trigger_check(entity: Entity):
    """
    Manual/on-demand endpoint to screen an entity for adverse media.
    """
    risk_event = MediaOrchestrator.process_entity(entity)
    if risk_event:
        return risk_event
    else:
        raise HTTPException(status_code=404, detail="No adverse media found for this entity.")

@app.post("/process-verdict", response_model=RiskEvent)
async def process_verdict(verdict: ResolutionVerdict):
    """
    Endpoint to receive a confirmed sanctions match from Person 2 and trigger an investigation.
    """
    risk_event = MediaOrchestrator.process_verdict(verdict)
    if risk_event:
        return risk_event
    else:
        raise HTTPException(status_code=200, detail="Verdict processed but no risk event triggered.")

from pydantic import BaseModel

class ScanFrequencyUpdate(BaseModel):
    minutes: int

@app.post("/update-frequency")
async def update_frequency(freq: ScanFrequencyUpdate):
    """
    Dynamically update the background scanning frequency without restarting the server.
    """
    if freq.minutes <= 0:
        raise HTTPException(status_code=400, detail="Minutes must be greater than 0")
        
    scheduler.reschedule_job("gdelt_poll_job", trigger="interval", minutes=freq.minutes)
    
    # Update the global variable just to keep it in sync for any subsequent reads
    global SCAN_FREQUENCY_MINUTES
    SCAN_FREQUENCY_MINUTES = freq.minutes
    
    print(f"[CONFIG] Background poller frequency updated dynamically to {freq.minutes} minutes.")
    return {"message": f"Scan frequency dynamically updated to {freq.minutes} minutes."}
