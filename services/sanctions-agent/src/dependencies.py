from fastapi import Request
from src.db import AuditLogger
from src.services.opensanctions import OpenSanctionsClient

def get_db_client(request: Request) -> AuditLogger:
    """Dependency provider for AuditLogger."""
    return request.app.state.db_client

def get_opensanctions_client(request: Request) -> OpenSanctionsClient:
    """Dependency provider for OpenSanctionsClient."""
    return request.app.state.opensanctions_client
