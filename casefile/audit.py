"""Append-only audit helpers and timeline reconstruction."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contracts.models import AuditEvent, TimelineEvent


def write(actor: str, action: str, object_type: str, object_id: str, rationale: str,
          *, before: dict | None = None, after: dict | None = None,
          at: datetime | None = None) -> AuditEvent:
    """Create an event for insertion into the append-only audit table.

    Persistence is deliberately kept in ``db.store`` so callers can append a case
    change and its audit event in the same transaction.
    """
    return AuditEvent(
        audit_id=f"AUD-{uuid4().hex}", at=at or datetime.now(timezone.utc), actor=actor,
        action=action, object_type=object_type, object_id=object_id,
        before=before, after=after, rationale=rationale,
    )


def timeline_from_events(events: list[AuditEvent]) -> list[TimelineEvent]:
    """Reconstruct a risk timeline solely from audit snapshots.

    Events without a tier transition are intentionally omitted: they remain in the
    audit trail but do not manufacture a risk-profile change.
    """
    timeline: list[TimelineEvent] = []
    seen_dedup_keys: set[str] = set()
    for event in sorted(events, key=lambda item: item.at):
        before, after = event.before or {}, event.after or {}
        old_tier, new_tier = before.get("tier"), after.get("tier")
        if old_tier is None or new_tier is None:
            continue
        dedup_key = after.get("dedup_key")
        # A news event is represented by its story cluster, not every outlet that
        # syndicated it. Regulatory revocations use a distinct key and therefore
        # remain a separate (often negative) risk movement.
        if dedup_key and dedup_key in seen_dedup_keys:
            continue
        if dedup_key:
            seen_dedup_keys.add(dedup_key)
        evidence_ids = after.get("evidence_ids", [])
        timeline.append(TimelineEvent(
            at=event.at,
            kind="REVIEW" if event.actor.startswith("user:") else "REASSESSMENT",
            summary=event.rationale,
            evidence_ids=evidence_ids,
            tier_before=old_tier,
            tier_after=new_tier,
            score_delta=float(after.get("score", 0)) - float(before.get("score", 0)),
            dedup_key=dedup_key,
            resolution_confidence=float(after.get("resolution_confidence", 1.0)),
        ))
    return timeline
