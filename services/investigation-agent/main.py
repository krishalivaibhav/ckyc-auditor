from fastapi import FastAPI

from models import (
    RiskEvent,
    InvestigationOutput,
    TimelineEvent,
    Citation,
    DraftReport,
)

from retrieval import (
    build_vector_database,
)

from report_generator import generate_report
from audit import write_audit_log

app = FastAPI(
    title="Investigation Agent",
    description="TechMKYC Investigation Service",
    version="1.0"
)


@app.on_event("startup")
def startup():

    print("Building vector database...")

    build_vector_database()

    print("Vector database ready.")


@app.get("/")
def home():

    return {
        "message": "Investigation Agent is running!"
    }


@app.post("/investigate", response_model=InvestigationOutput)
def investigate(risk_event: RiskEvent):

    # Generate report using retrieved evidence
    report_data = generate_report(risk_event)

    timeline = [
        TimelineEvent(**item)
        for item in report_data["timeline"]
    ]

    citations = [
        Citation(**item)
        for item in report_data["citations"]
    ]

    draft_report = DraftReport(
        summary=report_data["summary"],
        citations=citations
    )

    # Audit logging
    write_audit_log(
        action="generated_draft_report",
        entity_id=risk_event.entity_id
    )

    return InvestigationOutput(
        entity_id=risk_event.entity_id,
        timeline=timeline,
        draft_report=draft_report
    )