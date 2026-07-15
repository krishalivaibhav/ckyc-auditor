"""SNEHA. Append-only. Enforced by a DB rule, not by convention."""
from contracts.models import AuditEvent


def write(actor: str, action: str, object_type: str, object_id: str, rationale: str) -> AuditEvent:
    raise NotImplementedError("NO UPDATE. NO DELETE. timeline + audit trail both derive from here.")
