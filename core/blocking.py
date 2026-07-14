"""VAIBHAV. Rung 0 — blocking / candidate generation.

Never compare a customer against all ~18k watchlist entries. Block on cheap keys
and only resolve the handful that collide:

    normalised surname  ∪  first-initial + surname  ∪  phonetic(name)  ∪  PAN

Target: < 50 candidates / customer. The reduction ratio is a real, reportable
number (see `Blocker.stats`).

PHONETIC KEY: the design calls for Double Metaphone. jellyfish (already a
dependency) ships single Metaphone, not double; we use it here as the phonetic
blocking key. Blocking only widens recall of the candidate set — the actual
match/reject decisions are made deterministically by the resolver — so the exact
phonetic algorithm is not load-bearing. Swapping in true Double Metaphone is a
one-line change when the dependency lands.
"""
from collections import defaultdict

import jellyfish

from contracts.models import WatchlistEntry
from core.normalize import first_initial, normalize, surname, tokens


# ---------------------------------------------------------------- CSV -> contract
_STATUS = {
    "SABHA_PEP_CURRENT": "current",
    "SABHA_PEP_FORMER": "former",
}


def _entity_type(list_name: str, pan: str) -> str:
    """Best-effort type. OpenSanctions flattens everyone to LegalEntity; the PAN
    4th char gives person/company back for the debarred list."""
    if list_name == "NSE_SEBI_DEBARRED" and len(pan) == 10:
        return {"P": "Individual", "C": "Corporate"}.get(pan[3], "Organization")
    return "Individual"


def load_watchlist_entries(rows: list[dict]) -> list[WatchlistEntry]:
    """Convert canonical CSV rows (watchlist_id,list,name,pan,extra) into the
    frozen `WatchlistEntry` contract. `extra` is overloaded per list: status for
    debarred, party for PEP, ';'-joined aliases for UAPA."""
    out = []
    for r in rows:
        lst = r["list"]
        pan = (r.get("pan") or "").strip().upper()
        extra = (r.get("extra") or "").strip()
        aliases, party, status = [], None, _STATUS.get(lst, "active")
        if lst == "NSE_SEBI_DEBARRED":
            status = "revoked" if extra == "revoked" else "active"
        elif lst in ("SABHA_PEP_CURRENT", "SABHA_PEP_FORMER"):
            party = extra or None
        elif lst == "MHA_UAPA":
            aliases = [a.strip() for a in extra.split(";") if a.strip()]
        out.append(WatchlistEntry(
            watchlist_id=r["watchlist_id"], list=lst,
            entity_type=_entity_type(lst, pan), name=r["name"],
            aliases=aliases, pan=pan or None, party=party, status=status,
        ))
    return out


# ---------------------------------------------------------------- blocker
def _phonetic(name: str) -> str:
    """Phonetic signature of a full name: concatenated token metaphones."""
    return "".join(jellyfish.metaphone(t) for t in tokens(name))


class Blocker:
    """Inverted indices over the watchlist. Build once, query per customer."""

    def __init__(self, entries: list[WatchlistEntry]):
        self.entries = entries
        self.by_pan: dict[str, list[int]] = defaultdict(list)
        self.by_surname: dict[str, list[int]] = defaultdict(list)
        self.by_fi_surname: dict[tuple, list[int]] = defaultdict(list)
        self.by_phon_surname: dict[str, list[int]] = defaultdict(list)
        self.by_phon_full: dict[str, list[int]] = defaultdict(list)

        for i, e in enumerate(entries):
            if e.pan:
                self.by_pan[e.pan.upper()].append(i)
            # index the canonical name AND every alias (UAPA is name-only, and a
            # true positive may be recorded under an alias spelling).
            for nm in [e.name, *e.aliases]:
                sur = surname(nm)
                if not sur:
                    continue
                self.by_surname[sur].append(i)
                self.by_fi_surname[(first_initial(nm), sur)].append(i)
                self.by_phon_surname[jellyfish.metaphone(sur)].append(i)
                self.by_phon_full[_phonetic(nm)].append(i)

    def candidates(self, name: str, pan: str | None = None,
                   wide: bool = False) -> list[WatchlistEntry]:
        """Blocked candidate set for one customer, deduped by index.

        Default (tight) keys — everything Rungs 0-3 need:
            PAN  ∪  (first-initial + surname)  ∪  phonetic(full name)
        These surface every exact-name and PAN match while keeping the pool
        small (<50/customer). The bare `surname` / phonetic-surname keys are
        far coarser (common Indian surnames + corporate suffixes like 'LTD'
        pull >1000 rows) and only widen recall for the FUZZY rung, which tests
        dropped-first-name / initial-only variants. Callers on that rung pass
        wide=True to opt in.
        """
        idx: set[int] = set()
        if pan:
            idx.update(self.by_pan.get(pan.strip().upper(), ()))
        sur = surname(name)
        if sur:
            idx.update(self.by_fi_surname.get((first_initial(name), sur), ()))
            idx.update(self.by_phon_full.get(_phonetic(name), ()))
            if wide:
                idx.update(self.by_surname.get(sur, ()))
                idx.update(self.by_phon_surname.get(jellyfish.metaphone(sur), ()))
        return [self.entries[i] for i in idx]

    def stats(self, customers: list[dict]) -> dict:
        """Reduction-ratio report over a customer cohort."""
        counts = [len(self.candidates(c.get("client_name", ""), c.get("pan")))
                  for c in customers]
        n = len(counts) or 1
        avg = sum(counts) / n
        total = len(self.entries)
        return {
            "watchlist_size": total,
            "customers": len(counts),
            "avg_candidates": avg,
            "max_candidates": max(counts) if counts else 0,
            "reduction_ratio": (total / avg) if avg else float("inf"),
            "pct_over_50": sum(c > 50 for c in counts) / n,
        }
