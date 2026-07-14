import pytest
from fastapi.testclient import TestClient
import httpx
from unittest.mock import AsyncMock
from src.main import app
from src.dependencies import get_db_client, get_opensanctions_client

@pytest.fixture
def mock_db():
    """Mock for AuditLogger."""
    mock = AsyncMock()
    mock.log_screening.return_value = True
    return mock

@pytest.fixture
def mock_opensanctions():
    """Mock for OpenSanctionsClient."""
    mock = AsyncMock()
    mock.match_entity.return_value = [
        {
            "candidate_id": "NK-11111",
            "matched_name": "Johnathan Doe",
            "score": 0.85,
            "source_list": "Sanctions",
            "raw": {
                "id": "NK-11111",
                "caption": "Johnathan Doe",
                "properties": {
                    "birthDate": ["1980-01-01"],
                    "nationality": ["US"]
                }
            }
        }
    ]
    return mock

@pytest.fixture
def client(mock_db, mock_opensanctions):
    """Fixture providing TestClient with overridden dependencies."""
    app.dependency_overrides[get_db_client] = lambda: mock_db
    app.dependency_overrides[get_opensanctions_client] = lambda: mock_opensanctions
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()

def test_health_check(client):
    """Verify that health check endpoint returns success status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_screen_end_to_end(client, mock_db, mock_opensanctions):
    """Verify endpoint works end-to-end, performs fuzzy scoring, and logs exactly once."""
    test_entity = {
        "entity_id": "89eb5b10-e7f0-4592-8086-599187ea1320",
        "type": "person",
        "name": "John Doe",
        "aliases": ["Johnny Doe"],
        "dob": "1980-01-01",
        "nationality": "US",
        "din_or_cin": None,
        "source": "client_input"
    }
    response = client.post("/screen", json=test_entity)
    assert response.status_code == 200
    data = response.json()
    
    assert data["query_entity_id"] == "89eb5b10-e7f0-4592-8086-599187ea1320"
    assert len(data["candidates"]) == 1
    
    candidate = data["candidates"][0]
    assert candidate["candidate_id"] == "NK-11111"
    assert candidate["matched_name"] == "Johnathan Doe"
    # Merged score (local rapidfuzz name similarity score ~0.7826 and API score 0.85) should be ~0.8163
    assert 0.80 <= candidate["score"] <= 0.84
    assert "name" in candidate["matched_fields"]
    assert "dob" in candidate["matched_fields"]
    assert "nationality" in candidate["matched_fields"]
    
    # Verify that audit logging was invoked exactly once
    mock_db.log_screening.assert_called_once()
    call_args = mock_db.log_screening.call_args[0]
    assert call_args[0] == "89eb5b10-e7f0-4592-8086-599187ea1320"
    
    details = call_args[1]
    assert details["candidate_count"] == 1
    assert details["top_match_score"] == candidate["score"]
    assert set(details["matched_fields"]) == {"dob", "name", "nationality"}

def test_screen_invalid_payload(client):
    """Verify that invalid payload format (e.g. wrong type or missing fields) returns HTTP 422."""
    bad_entity = {
        "entity_id": "not-a-uuid",  # Invalid UUID
        "type": "person",
        "name": "",
        "source": "client_input"
    }
    response = client.post("/screen", json=bad_entity)
    assert response.status_code == 422

def test_screen_opensanctions_http_error(client, mock_opensanctions):
    """Verify that upstream HTTP errors return HTTP 502 Bad Gateway."""
    request = httpx.Request("POST", "http://mock-api")
    http_error = httpx.HTTPStatusError(
        message="Internal Server Error",
        request=request,
        response=httpx.Response(status_code=500, request=request)
    )
    mock_opensanctions.match_entity.side_effect = http_error

    test_entity = {
        "entity_id": "89eb5b10-e7f0-4592-8086-599187ea1320",
        "type": "person",
        "name": "John Doe",
        "source": "client_input"
    }
    response = client.post("/screen", json=test_entity)
    assert response.status_code == 502
    assert "Upstream database error" in response.json()["detail"]

def test_screen_opensanctions_network_error(client, mock_opensanctions):
    """Verify that upstream network errors return HTTP 503 Service Unavailable."""
    mock_opensanctions.match_entity.side_effect = httpx.RequestError(
        message="Connection timed out",
        request=httpx.Request("POST", "http://mock-api")
    )

    test_entity = {
        "entity_id": "89eb5b10-e7f0-4592-8086-599187ea1320",
        "type": "person",
        "name": "John Doe",
        "source": "client_input"
    }
    response = client.post("/screen", json=test_entity)
    assert response.status_code == 503
    assert "Upstream database unavailable" in response.json()["detail"]

def test_screen_audit_logger_failure_does_not_fail_request(client, mock_db):
    """Verify that if the audit logger raises an exception, the /screen response still succeeds with 200 OK."""
    # Audit logging throws exception (e.g. database down, file write permission issue)
    mock_db.log_screening.side_effect = Exception("System logs blocked")

    test_entity = {
        "entity_id": "89eb5b10-e7f0-4592-8086-599187ea1320",
        "type": "person",
        "name": "John Doe",
        "source": "client_input"
    }
    response = client.post("/screen", json=test_entity)
    
    # Must succeed (return 200 OK) since logging errors are fail-safe
    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) == 1
