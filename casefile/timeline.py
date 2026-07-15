"""Cumulative, audit-derived risk timelines.

Timeline entries represent risk events, not articles: callers pass a stable
``dedup_key`` (normally a story cluster or regulatory order) so five syndicated
articles become one entry.  Score movement is additive and may be negative.
"""
from __future__ import annotations

from collections.abc import Iterable

from contracts.models import AuditEvent, TimelineEvent
from casefile.audit import timeline_from_events


def append_event(timeline: list[TimelineEvent], event: TimelineEvent) -> list[TimelineEvent]:
    """Add a risk event unless the same real-world event was already recorded.

    A duplicate article never changes cumulative risk. A later regulatory delta
    with a different key may lower it; negative ``score_delta`` is intentional.
    """
    if event.dedup_key and any(item.dedup_key == event.dedup_key for item in timeline):
        return list(timeline)
    return sorted([*timeline, event], key=lambda item: item.at)


def current_score(timeline: Iterable[TimelineEvent]) -> float:
    """The running score, including decay/revocation de-escalations."""
    return round(sum(event.score_delta for event in timeline), 6)


def reconstruct_timeline(events: list[AuditEvent], client_id: str | None = None) -> list[TimelineEvent]:
    """Rebuild the timeline exclusively from immutable audit events.

    New audit writers should place ``tier``, ``score``, ``evidence_ids`` and an
    optional ``dedup_key`` in their before/after snapshots. Older fixture events
    without snapshots remain auditable but cannot honestly be turned into a
    timeline transition, so they are not invented here.
    """
    if client_id:
        events = [event for event in events if event.object_id == client_id
                  or (event.after or {}).get("client_id") == client_id]
    return timeline_from_events(events)
