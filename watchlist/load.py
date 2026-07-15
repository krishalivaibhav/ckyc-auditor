"""Fast access to Mohita's canonical watchlist artifact."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from contracts.models import WatchlistEntry

PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "Unknown", "F": "Unknown", "T": "Unknown"}

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CANONICAL_PATH = DATA_DIR / "watchlist_canonical.json"
DETAILS_PATH = DATA_DIR / "watchlist_details.json"
RELATIONSHIPS_PATH = DATA_DIR / "watchlist_relationships.json"

# Two-word aliases in this set are deliberately unsafe despite having two words.
COMMON_INDIAN_NAMES = frozenset({
    "amir khan", "gulshan kumar", "abdul manan", "salim", "salman", "hamza",
    "zakir", "ismail", "sultan", "aziz", "mustafa", "mushtaq", "sikander",
    "fareed", "khursheed", "mufti", "moulvi", "ustad", "doctor", "chief", "chacha",
})


def classify_alias(alias: str) -> str:
    """Classify MHA aliases so bare names can never trigger by themselves."""
    import re

    value = " ".join(alias.strip().split())
    if re.fullmatch(r"\(?[A-Z][A-Z\-()]{1,7}\)?", value):
        return "org_acronym"
    if len(value.split()) == 1 or value.casefold() in COMMON_INDIAN_NAMES:
        return "bare_token"
    return "full_name"


@lru_cache(maxsize=1)
def load_watchlist() -> list[WatchlistEntry]:
    """Load the compiled artifact. Run ``python -m watchlist.build`` once first."""
    if not CANONICAL_PATH.exists():
        raise FileNotFoundError(
            f"{CANONICAL_PATH.name} does not exist. Run `python -m watchlist.build` first."
        )
    with CANONICAL_PATH.open(encoding="utf-8") as handle:
        return [WatchlistEntry.model_validate(item) for item in json.load(handle)]


def load_all() -> list[WatchlistEntry]:
    """Backward-compatible name for the original package stub."""
    return load_watchlist()


@lru_cache(maxsize=1)
def load_details() -> dict[str, dict]:
    if not DETAILS_PATH.exists():
        return {}
    with DETAILS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_relationships() -> dict[str, list[dict]]:
    if not RELATIONSHIPS_PATH.exists():
        return {}
    with RELATIONSHIPS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def relatives(watchlist_id: str) -> list[WatchlistEntry]:
    """Return known Sabha relatives/associates of a canonical entry."""
    entries = {entry.watchlist_id: entry for entry in load_watchlist()}
    return [entries[item["watchlist_id"]] for item in load_relationships().get(watchlist_id, [])
            if item["watchlist_id"] in entries]
