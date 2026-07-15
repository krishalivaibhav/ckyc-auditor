"""Verify a sanctions-agent hit through the ER ladder.

The connection point between the two agents. The **sanctions agent** watches for
sanctions imposed in near-real-time; on a hit it hands off the customer plus the
matched watchlist entries. This module runs the deterministic resolver (Rungs 0-3)
over that hit and returns a verdict:

    CONFIRMED  — same entity (e.g. PAN exact). A real alert.
    SUPPRESSED — name collides but identifiers say it is a different entity
                 (PAN_MISMATCH_REJECT / TYPE_MISMATCH_REJECT). The false positive
                 we refuse to raise — every one carries a plain-language reason.
    AMBIGUOUS  — resolver could not settle it deterministically (later rungs / human).
    NO_MATCH   — blocking surfaced the entry but nothing asserts a match.

The REJECTED candidates with their `rejection_reason` are the product — they feed
the suppression log.
"""
from contracts.models import Customer, WatchlistEntry
from core.resolver import resolve


def verify_hit(customer: Customer, candidates: list[WatchlistEntry]) -> dict:
    """Run the resolver over a sanctions hit and summarise the verdict."""
    verdicts = resolve(customer, candidates)
    confirmed = [c for c in verdicts if c.decision == "CONFIRMED"]
    rejected = [c for c in verdicts if c.decision == "REJECTED"]
    ambiguous = [c for c in verdicts if c.decision == "AMBIGUOUS"]

    if confirmed:
        verdict = "CONFIRMED"
    elif ambiguous:
        verdict = "AMBIGUOUS"
    elif rejected:
        verdict = "SUPPRESSED"
    else:
        verdict = "NO_MATCH"

    return {
        "client_id": customer.client_id,
        "client_name": customer.client_name,
        "verdict": verdict,
        "confirmed": bool(confirmed),
        "candidates": [c.model_dump(mode="json") for c in verdicts],
        "suppressions": [
            {"watchlist_id": c.watchlist_id, "method": c.match_method,
             "reason": c.rejection_reason}
            for c in rejected
        ],
    }
