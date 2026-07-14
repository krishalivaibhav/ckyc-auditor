import os
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock
from src.db import AuditLogger

def run_async(coro):
    """Utility to execute async functions synchronously."""
    return asyncio.run(coro)

@patch("psycopg2.connect")
def test_audit_logging_success(mock_connect):
    """Verify that AuditLogger logs successfully to database when DB is online."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    logger_instance = AuditLogger(db_url="postgresql://mock-db/techmkyc")
    entity_id = "89eb5b10-e7f0-4592-8086-599187ea1320"
    details = {"match_count": 3, "status": "reviewed"}

    res = run_async(logger_instance.log_screening(entity_id, details))
    
    assert res is True
    mock_connect.assert_called_once_with("postgresql://mock-db/techmkyc", connect_timeout=3)
    mock_cursor.execute.assert_any_call("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        log_id UUID PRIMARY KEY,
                        actor VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        entity_id UUID NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        details JSONB NOT NULL
                    );
                """)
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()

@patch("psycopg2.connect")
def test_audit_logging_db_failure_file_fallback(mock_connect, tmp_path):
    """Verify that when database fails, the logger falls back to JSONL file storage gracefully."""
    # DB connection throws exception
    mock_connect.side_effect = Exception("DB connection timeout")

    fallback_file = tmp_path / "test_audit.jsonl"
    logger_instance = AuditLogger(
        db_url="postgresql://mock-db/techmkyc", 
        fallback_file_path=str(fallback_file)
    )
    entity_id = "89eb5b10-e7f0-4592-8086-599187ea1320"
    details = {"match_count": 0, "status": "no_match"}

    res = run_async(logger_instance.log_screening(entity_id, details))
    
    # Must succeed (return True) due to fallback file logic
    assert res is True
    assert os.path.exists(fallback_file)
    
    # Read the written JSON line
    with open(fallback_file, "r") as f:
        log_line = json.loads(f.readline())
        
    assert log_line["actor"] == "agent:sanctions-agent"
    assert log_line["action"] == "screened_entity"
    assert log_line["entity_id"] == entity_id
    assert log_line["details"] == details
    assert "log_id" in log_line
    assert "timestamp" in log_line

@patch("psycopg2.connect")
def test_audit_logging_total_failure_no_crash(mock_connect):
    """Verify that if both DB and file logging fail, it returns False and does not raise an exception."""
    mock_connect.side_effect = Exception("DB down")

    # Invalid filename path that fails open()
    logger_instance = AuditLogger(
        db_url="postgresql://mock-db/techmkyc", 
        fallback_file_path="/invalid_dir/does_not_exist/test.jsonl"
    )
    entity_id = "89eb5b10-e7f0-4592-8086-599187ea1320"
    
    res = run_async(logger_instance.log_screening(entity_id, {}))
    
    # Returns False instead of throwing/crashing the thread
    assert res is False

def test_audit_logging_invalid_entity_id():
    """Verify that invalid UUID formats fail validation and return False immediately."""
    logger_instance = AuditLogger(db_url="postgresql://mock-db/techmkyc")
    res = run_async(logger_instance.log_screening("invalid-uuid-string", {}))
    
    assert res is False
