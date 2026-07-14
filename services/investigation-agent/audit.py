import json
from datetime import datetime
from pathlib import Path

AUDIT_FILE = Path("audit_log.json")


def write_audit_log(action: str, entity_id: str):
    """
    Append an audit entry whenever an investigation report is generated.
    """

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "entity_id": entity_id
    }

    logs = []

    if AUDIT_FILE.exists():
        with open(AUDIT_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(entry)

    with open(AUDIT_FILE, "w") as f:
        json.dump(logs, f, indent=4)