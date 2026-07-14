import uuid
import datetime
import json
import logging
import psycopg2
from psycopg2.extras import Json
from typing import Dict, Any

logger = logging.getLogger("sanctions-agent.db")

class AuditLogger:
    """
    Manages writing log records to the centralized append-only audit trail.
    Adheres strictly to the schema specified in docs/schema.md §6.
    """
    def __init__(self, db_url: str, fallback_file_path: str = "audit_logs.jsonl"):
        self.db_url = db_url
        self.fallback_file_path = fallback_file_path

    async def log_screening(self, entity_id: str, details: Dict[str, Any]) -> bool:
        """
        Creates and writes an audit log entry for a screening action.
        Guarantees no crashes on database exceptions.
        """
        # Validate entity_id is a valid UUID
        try:
            uuid.UUID(str(entity_id))
        except ValueError as err:
            logger.error(f"Failed to log screening: invalid entity_id format '{entity_id}'.")
            return False

        log_entry = {
            "log_id": str(uuid.uuid4()),
            "actor": "agent:sanctions-agent",
            "action": "screened_entity",
            "entity_id": str(entity_id),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "details": details
        }

        # Try writing to Postgres DB
        try:
            self._write_to_db(log_entry)
            logger.info(f"Successfully logged screening event {log_entry['log_id']} to PostgreSQL database.")
            return True
        except Exception as db_err:
            logger.warning(f"Database logging failed, using fallback file storage: {db_err}")
            
            # Fallback to appending JSON lines file
            try:
                self._write_to_file(log_entry)
                logger.info(f"Successfully logged screening event {log_entry['log_id']} to fallback file: {self.fallback_file_path}")
                return True
            except Exception as file_err:
                logger.error(f"Fallback file logging also failed: {file_err}")
                return False

    def _write_to_db(self, entry: Dict[str, Any]) -> None:
        """Helper to synchronously insert log entry into Postgres DB."""
        if not self.db_url or "postgresql" not in self.db_url:
            raise ValueError("No database URL provided or invalid URL format.")
            
        conn = None
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        log_id UUID PRIMARY KEY,
                        actor VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        entity_id UUID NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        details JSONB NOT NULL
                    );
                """)
                cur.execute(
                    """
                    INSERT INTO audit_logs (log_id, actor, action, entity_id, timestamp, details)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        entry["log_id"],
                        entry["actor"],
                        entry["action"],
                        entry["entity_id"],
                        entry["timestamp"],
                        Json(entry["details"])
                    )
                )
                conn.commit()
        finally:
            if conn:
                conn.close()

    def _write_to_file(self, entry: Dict[str, Any]) -> None:
        """Appends log entry to a JSONL file."""
        with open(self.fallback_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

