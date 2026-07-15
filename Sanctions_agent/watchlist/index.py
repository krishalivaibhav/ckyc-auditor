"""Small, deterministic candidate index for the resolver."""
from __future__ import annotations

import re
from collections import defaultdict

from contracts.models import WatchlistEntry
from watchlist.load import load_watchlist

_TITLES = re.compile(r"\b(?:shri|shrimati|smt|mr|mrs|ms|dr|mohd|mohammed)\.?\s*", re.I)
_NON_WORD = re.compile(r"[^a-z0-9\s]")


def normalize_name(value: str) -> str:
    value = value.strip()
    if "," in value:
        left, right = (part.strip() for part in value.split(",", 1))
        value = f"{right} {left}"
    value = _TITLES.sub("", value)
    return " ".join(_NON_WORD.sub(" ", value.casefold()).split())


def soundex(value: str) -> str:
    """Dependency-free phonetic blocking key; never a confirmation decision."""
    letters = re.sub("[^a-z]", "", value.casefold())
    if not letters:
        return ""
    codes = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"),
             **dict.fromkeys("dt", "3"), "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}
    tail, previous = [], codes.get(letters[0], "")
    for char in letters[1:]:
        code = codes.get(char, "")
        if code and code != previous:
            tail.append(code)
        previous = code
    return (letters[0].upper() + "".join(tail) + "000")[:4]


class ScreeningIndex:
    def __init__(self, entries: list[WatchlistEntry] | None = None) -> None:
        self.entries = entries if entries is not None else load_watchlist()
        self.by_pan: dict[str, WatchlistEntry] = {}
        self.by_name: dict[str, list[WatchlistEntry]] = defaultdict(list)
        self.by_phonetic: dict[str, list[WatchlistEntry]] = defaultdict(list)
        self.by_surname_block: dict[str, list[WatchlistEntry]] = defaultdict(list)
        for entry in self.entries:
            if entry.pan:
                self.by_pan.setdefault(entry.pan.upper(), entry)
            for value in [entry.name, *entry.aliases]:
                normalized = normalize_name(value)
                if not normalized:
                    continue
                # Bare aliases are kept in the data but cannot expand a candidate search.
                if value in entry.alias_quality and entry.alias_quality[value] == "bare_token":
                    continue
                self.by_name[normalized].append(entry)
                self.by_phonetic[soundex(normalized)].append(entry)
                self.by_surname_block[normalized.split()[-1]].append(entry)

    def candidates(self, name: str, pan: str | None = None) -> list[WatchlistEntry]:
        """Return a bounded candidate set, prioritising deterministic identifiers."""
        if pan and pan.upper() in self.by_pan:
            return [self.by_pan[pan.upper()]]
        normalized = normalize_name(name)
        candidates = list(self.by_name.get(normalized, []))
        if not candidates and normalized:
            candidates = list(self.by_phonetic.get(soundex(normalized), []))
        if not candidates and normalized:
            candidates = list(self.by_surname_block.get(normalized.split()[-1], []))
        seen: set[str] = set()
        return [entry for entry in candidates if not (entry.watchlist_id in seen or seen.add(entry.watchlist_id))][:49]
