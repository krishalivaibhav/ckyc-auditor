"""Near-real-time ingest adapters — where the producer agents plug in.

Two producers push events at this service:

    sanctions monitor (Sanctions_agent/watchlist/monitor.py)
        POST /api/ingest        {customer, candidates, trigger}
        The monitor already screened the customer book, so the hit arrives as
        contract objects: the Customer plus the WatchlistEntry entries it matched.

    news agent (news_agent/signals/emitter.py)
        POST /signals/ingest    the news agent's own Signal JSON (name-only!)
        A DIFFERENT lineage with its own models — entity_name/severity-word/
        triage_reasoning, no PAN, no contract types. This module adapts it:
        resolve entity_name against the customer book, translate the payload
        into a contracts.models.Signal, then run the same pipeline.

Both paths converge on core.orchestrator.run_pipeline(customer,
external_signals=..., extra_watchlist=...): verify (ER ladder) -> assess ->
investigate -> SAR -> persist, with the trigger landing on the Case timeline.
"""
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from contracts.models import Customer, Signal
from core.normalize import normalize

FIX = Path(__file__).resolve().parents[1] / "fixtures"

# news-agent severity words -> the contract's 0..1 severity score
_SEVERITY = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 0.95}

# keyword -> contracts RiskTypology. Scanned over headline + triage reasoning.
_TYPOLOGY = [
    ("sanction", "SANCTIONS"), ("launder", "MONEY_LAUNDERING"),
    ("terror", "TERRORISM"), ("uapa", "TERRORISM"), ("fraud", "FRAUD"),
    ("bribe", "CORRUPTION"), ("corrupt", "CORRUPTION"),
    ("manipulat", "MARKET_MANIPULATION"),
    ("sebi", "REGULATORY_ACTION"), ("debar", "REGULATORY_ACTION"),
    ("regulat", "REGULATORY_ACTION"),
]


def _customers() -> list[Customer]:
    return [Customer(**c) for c in json.loads((FIX / "customers.json").read_text())]


def find_customers(name: str) -> list[Customer]:
    """Resolve a bare entity name from the news agent against the customer book.
    Normalised exact match — the shared dataset means every watched name IS a
    customer name. Returns ALL matches: 'Dipak Dwiwedi' is two distinct clients,
    and each must be adjudicated separately (that ambiguity is the product)."""
    target = normalize(name)
    return [c for c in _customers() if normalize(c.client_name) == target] if target else []


def _parse_dt(value, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return fallback


def news_signal_to_contract(payload: dict) -> Signal:
    """news_agent Signal JSON -> contracts.models.Signal (ADVERSE_MEDIA)."""
    now = datetime.now(timezone.utc)
    headline = payload.get("headline", "")
    url = payload.get("url", "")
    text = (headline + " " + payload.get("triage_reasoning", "")).lower()
    typologies = sorted({t for kw, t in _TYPOLOGY if kw in text})
    severity_word = str(payload.get("severity", "medium")).lower()

    return Signal(
        signal_id=payload.get("signal_id") or f"NEWS-{uuid4().hex[:12]}",
        signal_type="ADVERSE_MEDIA",
        occurred_at=_parse_dt(payload.get("published_at"), now),
        ingested_at=_parse_dt(payload.get("detected_at"), now),
        source=payload.get("source_name") or "adverse media",
        source_url=url,
        source_credibility=float(payload.get("confidence", 0.5)),
        headline=headline,
        raw_excerpt=(payload.get("triage_reasoning") or headline)[:300],
        content_hash=sha256(f"{headline.strip().lower()}|{url.strip().lower()}"
                            .encode()).hexdigest(),
        mentioned_names=[payload["entity_name"]] if payload.get("entity_name") else [],
        risk_typology=typologies,
        severity=_SEVERITY.get(severity_word, 0.5),
    )


def sanctions_trigger_to_contract(trigger: dict) -> Signal:
    """sanctions monitor 'trigger' block -> contracts.models.Signal (WATCHLIST_DELTA)."""
    now = datetime.now(timezone.utc)
    name = trigger.get("sanctioned_name", "")
    status = trigger.get("status", "active")
    urls = trigger.get("source_url") or []
    digest = sha256(f"{trigger.get('watchlist_id', '')}|{status}|"
                    f"{trigger.get('effective_at', '')}".encode()).hexdigest()
    return Signal(
        signal_id=f"WL-{digest[:16]}",
        signal_type="WATCHLIST_DELTA",
        occurred_at=_parse_dt(trigger.get("effective_at"), now),
        ingested_at=now,
        source="NSE_CIRCULAR",
        source_url=urls[0] if urls else "",
        source_credibility=1.0,
        headline=f"Watchlist {'revocation' if status == 'revoked' else 'addition'}: "
                 f"{name} ({trigger.get('list', '?')})",
        raw_excerpt=f"{name} watchlist status is {status}.",
        content_hash=digest,
        mentioned_names=[name] if name else [],
        risk_typology=["REGULATORY_ACTION"],
        severity=0.9 if status == "active" else 0.0,
    )
