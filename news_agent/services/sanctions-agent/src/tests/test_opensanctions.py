import pytest
import asyncio
import httpx
from unittest.mock import patch
from src.services.opensanctions import OpenSanctionsClient
from src.schemas import Entity

def run_async(coro):
    """Utility to execute async functions synchronously."""
    return asyncio.run(coro)

@patch("httpx.AsyncClient.post")
def test_opensanctions_client_success(mock_post):
    """Verify that client correctly handles successful match query and formats response."""
    # Create request and response
    request = httpx.Request("POST", "http://mock-api")
    mock_response = httpx.Response(
        status_code=200,
        json={
            "responses": {
                "q1": {
                    "results": [
                        {
                            "id": "NK-12345",
                            "caption": "Johnathan Doe",
                            "score": 0.92,
                            "schema": "Person",
                            "datasets": ["us_ofac", "eu_fsf"],
                            "properties": {
                                "topics": ["sanction"]
                            }
                        }
                    ]
                }
            }
        },
        request=request
    )
    mock_post.return_value = mock_response

    client = OpenSanctionsClient(api_key="test_key", base_url="http://mock-api")
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="John Doe",
        aliases=["Johnny"],
        dob="1990-01-01",
        nationality="US",
        din_or_cin=None,
        source="client_input"
    )

    results = run_async(client.match_entity(entity))
    
    # Assert correct payload structure was sent
    mock_post.assert_called_once()
    called_args, called_kwargs = mock_post.call_args
    assert called_kwargs["headers"] == {"Authorization": "ApiKey test_key"}
    
    sent_payload = called_kwargs["json"]
    assert "queries" in sent_payload
    q = sent_payload["queries"]["q1"]
    assert q["schema"] == "Person"
    assert q["properties"]["name"] == ["John Doe", "Johnny"]
    assert q["properties"]["birthDate"] == ["1990-01-01"]
    assert q["properties"]["nationality"] == ["US"]
    
    # Assert parsed response conforms to Candidate layout
    assert len(results) == 1
    candidate = results[0]
    assert candidate["candidate_id"] == "NK-12345"
    assert candidate["matched_name"] == "Johnathan Doe"
    assert candidate["score"] == 0.92
    assert candidate["source_list"] == "Sanctions"

@patch("httpx.AsyncClient.post")
def test_opensanctions_client_retry_and_recover(mock_post):
    """Verify that client retries on network transient failures and recovers on success."""
    request = httpx.Request("POST", "http://mock-api")
    fail_response = httpx.Response(status_code=502, request=request)
    success_response = httpx.Response(
        status_code=200,
        json={
            "responses": {
                "q1": {
                    "results": []
                }
            }
        },
        request=request
    )

    # First attempt fails, second succeeds
    mock_post.side_effect = [fail_response, success_response]

    client = OpenSanctionsClient(api_key="test_key", base_url="http://mock-api")
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="John Doe",
        source="client_input"
    )

    # Call method with low backoff to speed up execution
    results = run_async(client.match_entity(entity, max_retries=3, base_delay=0.01))
    
    assert mock_post.call_count == 2
    assert len(results) == 0

@patch("httpx.AsyncClient.post")
def test_opensanctions_client_max_retries_reached(mock_post):
    """Verify that client propagates exception after exceeding max_retries limit."""
    request = httpx.Request("POST", "http://mock-api")
    fail_response = httpx.Response(status_code=401, request=request)
    mock_post.return_value = fail_response

    client = OpenSanctionsClient(api_key="test_key", base_url="http://mock-api")
    entity = Entity(
        entity_id="89eb5b10-e7f0-4592-8086-599187ea1320",
        type="person",
        name="John Doe",
        source="client_input"
    )

    with pytest.raises(httpx.HTTPStatusError):
        run_async(client.match_entity(entity, max_retries=2, base_delay=0.01))
        
    assert mock_post.call_count == 2
