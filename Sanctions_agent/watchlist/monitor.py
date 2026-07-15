"""Near-real-time sanctions monitor → hands each hit to the ambiguity agent.

The connection between the two agents:

    watchlist deltas (sanctions imposed, in time order)   ── this file, sanctions side
        │  screen the customer book (ScreeningIndex)
        ▼  a HIT = (customer, matched watchlist entry)
        │  POST /api/ingest            (--verify-only hits /api/verify instead)
        ▼
    the pipeline service (ambiguity ER + investigation, one process)
        →  verify: CONFIRMED | SUPPRESSED (name collision) | AMBIGUOUS | NO_MATCH
        →  then assess -> investigate -> SAR -> persist Case to the SQLite sink

Production feed: `watchlist.replay.replay()` streams real NSE-circular deltas (needs
the built `data/watchlist_details.json` artifact). Until that is built this monitor
derives the same chronological "sanction imposed" stream from the loaded watchlist
entries themselves, so it runs on `fixtures/watchlist.json` today.

Run (ambiguity agent must be serving, default on :8001):
    python -m watchlist.monitor                       # POST hits to the verifier
    python -m watchlist.monitor --dry-run             # just print the hits found
    python -m watchlist.monitor --base-url http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Iterator

from contracts.models import Customer, WatchlistEntry
from watchlist.index import ScreeningIndex

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
DEFAULT_BASE_URL = "http://127.0.0.1:8001"   # the pipeline service (investigation_agent)


# ──────────────────────────────────────────────────────────────── data loading
def load_customers(path: Path | None = None) -> list[Customer]:
    path = path or (FIXTURES / "customers.json")
    return [Customer(**c) for c in json.loads(path.read_text())]


def load_entries(path: Path | None = None) -> list[WatchlistEntry]:
    path = path or (FIXTURES / "watchlist.json")
    return [WatchlistEntry(**w) for w in json.loads(path.read_text())]


def _effective_dt(entry: WatchlistEntry) -> datetime:
    """When this sanction became effective — used to order the near-real-time feed."""
    if entry.last_change:
        return entry.last_change
    if entry.order_date:
        return datetime.combine(entry.order_date, time.min, tzinfo=timezone.utc)
    if entry.first_seen:
        return entry.first_seen
    return datetime.min.replace(tzinfo=timezone.utc)


# ──────────────────────────────────────────────────────────────── the monitor
class SanctionHit:
    """One (customer, matched watchlist entry) pair — the sanctions agent's output."""

    def __init__(self, customer: Customer, entry: WatchlistEntry, at: datetime):
        self.customer = customer
        self.entry = entry
        self.at = at

    def event(self) -> dict:
        """The payload sent to the ambiguity agent's /api/verify."""
        return {
            "customer": self.customer.model_dump(mode="json"),
            "candidates": [self.entry.model_dump(mode="json")],
            "trigger": {
                "watchlist_id": self.entry.watchlist_id, "list": self.entry.list,
                "sanctioned_name": self.entry.name, "status": self.entry.status,
                "effective_at": self.at.isoformat(),
                "source_url": self.entry.source_url,
            },
        }


def find_hits(entries: list[WatchlistEntry],
              customers: list[Customer]) -> Iterator[SanctionHit]:
    """Stream sanctions imposed in chronological order and, for each, yield the
    customer(s) it screens onto. A newly-active sanction on entry E hits customer C
    when C's deterministic screening surfaces E (PAN or name/phonetic block)."""
    index = ScreeningIndex(entries)
    active = sorted((e for e in entries if e.status == "active"), key=_effective_dt)
    for entry in active:
        for cust in customers:
            matched = index.candidates(cust.client_name, cust.pan)
            if any(m.watchlist_id == entry.watchlist_id for m in matched):
                yield SanctionHit(cust, entry, _effective_dt(entry))


def post_hit(base_url: str, path: str, payload: dict,
             timeout: float = 30.0) -> dict | None:
    """POST a hit to the pipeline service. Degrades (returns None) on any
    transport failure so one unreachable call never kills the monitor."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  ! pipeline returned {e.code}: {e.read().decode()[:200]}")
    except urllib.error.URLError as e:
        print(f"  ! could not reach the pipeline at {base_url}: {e.reason}")
    return None


def run(base_url: str = DEFAULT_BASE_URL, dry_run: bool = False,
        verify_only: bool = False, limit: int | None = None) -> list[dict]:
    """Stream sanction hits into the pipeline. Default path is /api/ingest —
    verify + investigate + SAR + persist, so each hit becomes (or updates) a
    persisted Case the dashboard renders. --verify-only hits /api/verify instead
    (verdict printed, nothing persisted)."""
    entries, customers = load_entries(), load_customers()
    results: list[dict] = []
    n = 0
    for hit in find_hits(entries, customers):
        n += 1
        if limit and n > limit:
            break
        print(f"[HIT] {hit.at.date()}  sanction '{hit.entry.name}' ({hit.entry.list}) "
              f"→ customer {hit.customer.client_id} '{hit.customer.client_name}'")
        if dry_run:
            continue
        path = "/api/verify" if verify_only else "/api/ingest"
        out = post_hit(base_url, path, hit.event())
        if out is None:
            continue
        results.append(out)
        supp = out.get("suppressions") or []
        detail = (f" — {supp[0]['method']}: {supp[0]['reason']}"
                  if out.get("verdict") == "SUPPRESSED" and supp else "")
        case = out.get("case")
        case_note = (f"  [{case['case_id']} status={case['status']} tier={case['tier']}"
                     f"{' SAR drafted' if case.get('sar_drafted') else ''}]"
                     if case else "")
        print(f"      → verdict: {out.get('verdict')}{detail}{case_note}")
    if not dry_run:
        confirmed = sum(r.get("verdict") == "CONFIRMED" for r in results)
        suppressed = sum(r.get("verdict") == "SUPPRESSED" for r in results)
        print(f"\n{n} hit(s): {confirmed} CONFIRMED, {suppressed} SUPPRESSED, "
              f"{len(results) - confirmed - suppressed} other.")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help="pipeline service base URL")
    ap.add_argument("--dry-run", action="store_true",
                    help="find and print hits without POSTing them")
    ap.add_argument("--verify-only", action="store_true",
                    help="POST to /api/verify (verdict only, no case persisted)")
    ap.add_argument("--limit", type=int, default=None, help="stop after N hits")
    args = ap.parse_args()
    run(base_url=args.base_url, dry_run=args.dry_run,
        verify_only=args.verify_only, limit=args.limit)


if __name__ == "__main__":
    main()
