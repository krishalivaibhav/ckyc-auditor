"""Name similarity scoring — rapidfuzz (string) + jellyfish (phonetic).

We never rely on a single metric. The final name score blends a fuzzy
string-similarity component with a phonetic-agreement component so that
"Catherine" / "Katharine" style spelling variants still score high, while
genuinely different names score low.
"""

from __future__ import annotations

import jellyfish
from rapidfuzz import fuzz


def _phonetic_agreement(a: str, b: str) -> float:
    """1.0 if the two names agree on metaphone OR soundex, else 0.0."""
    a, b = a.strip(), b.strip()
    if not a or not b:
        return 0.0
    if jellyfish.metaphone(a) == jellyfish.metaphone(b):
        return 1.0
    if jellyfish.soundex(a) == jellyfish.soundex(b):
        return 1.0
    return 0.0


def name_similarity(a: str, b: str) -> float:
    """Blended similarity in [0.0, 1.0] between two names.

    70% fuzzy string match (token-sort handles word reordering) + 30%
    phonetic agreement.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    fuzzy = fuzz.token_sort_ratio(a.lower(), b.lower()) / 100.0
    phonetic = _phonetic_agreement(a, b)
    return round(0.70 * fuzzy + 0.30 * phonetic, 4)


def best_name_score(candidate_name: str, entity_name: str,
                    aliases: list[str] | None = None) -> float:
    """Best similarity of candidate_name against the entity's name + aliases."""
    names = [entity_name, *(aliases or [])]
    return max((name_similarity(candidate_name, n) for n in names), default=0.0)
