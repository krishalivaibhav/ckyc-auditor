"""Replay historical watchlist changes as contract ``Signal`` objects."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from hashlib import sha256
from typing import Iterator

from contracts.models import Signal
from watchlist.load import load_details


def _as_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def replay(start: date, end: date, speed: int = 1000) -> Iterator[Signal]:
    """Yield additions, changes, and revocations in chronological order.

    ``speed`` is deliberately accepted by the public API although yielding is non-blocking;
    the UI/orchestrator decides how quickly to consume the iterator.
    """
    if speed <= 0:
        raise ValueError("speed must be positive")
    if end < start:
        raise ValueError("end must not be before start")

    events: list[tuple[datetime, dict, dict]] = []
    for watchlist_id, detail in load_details().items():
        for order in detail.get("orders", []):
            order_date = order.get("order_date")
            if order_date:
                at = datetime.combine(date.fromisoformat(order_date), time.min, tzinfo=timezone.utc)
                events.append((at, detail, {**order, "event": "ADDED", "watchlist_id": watchlist_id}))
            end_date = order.get("end_date")
            if end_date:
                at = datetime.combine(date.fromisoformat(end_date), time.min, tzinfo=timezone.utc)
                events.append((at, detail, {**order, "event": "REVOKED", "watchlist_id": watchlist_id}))

        last_change = _as_datetime(detail.get("last_change"))
        if last_change:
            events.append((last_change, detail, {
                "event": "CHANGED", "watchlist_id": watchlist_id,
                "source_urls": detail.get("source_urls", []),
            }))

    for occurred_at, detail, event in sorted(events, key=lambda item: item[0]):
        if not start <= occurred_at.date() <= end:
            continue
        action = event["event"].lower()
        name = detail.get("canonical_name", event["watchlist_id"])
        status = "revoked" if event["event"] == "REVOKED" else "active"
        url = (event.get("source_urls") or detail.get("source_urls") or [""])[0]
        digest = sha256(f"{event['watchlist_id']}|{action}|{occurred_at.isoformat()}".encode()).hexdigest()
        yield Signal(
            signal_id=f"WL-{digest[:16]}", signal_type="WATCHLIST_DELTA",
            occurred_at=occurred_at, ingested_at=occurred_at, source="NSE_CIRCULAR",
            source_url=url, source_credibility=1.0,
            headline=f"Watchlist {action}: {name}",
            raw_excerpt=f"{name} watchlist status is {status}.", content_hash=digest,
            mentioned_names=[name], severity=0.9 if status == "active" else 0.0,
            risk_typology=["REGULATORY_ACTION"],
        )


class ReplayClock:
    """Compatibility wrapper used by the original brief."""

    def run(self, start: date, end: date, speed: int = 1000) -> Iterator[Signal]:
        return replay(start, end, speed)
