"""VAIBHAV. Deterministic name normalisation — Rung 0's foundation.

The bank's book is messy; the regulator's list is canonical. This module makes
the two comparable WITHOUT fuzzy matching:

  * strip honorifics (Shri / Shrimati / Smt / Dr / Mohd / ...)
  * invert "SURNAME, First"  ->  "First SURNAME"   (deterministic, not fuzzy)
  * drop punctuation, collapse whitespace, upper-case

This is normalisation, not matching. It recovers reorder/honorific noise for
free (a comma-inverted true positive becomes an exact match again). Typos and
transliteration are NOT handled here — that is the phonetic/fuzzy rung, later.
"""
import re
import unicodedata

# Leading honorifics we strip. Mirrors eval/build_portfolio's noise injector so a
# "Shri "-prefixed customer name normalises back onto its canonical form.
HON = re.compile(r"^(shri|shrimati|smt|mr|mrs|ms|dr|prof|sh|md|mohd)\.?\s+", re.I)


def normalize(s: str) -> str:
    """Return the canonical comparison key for a name.

    "Shri Aditya Reddy"  -> "ADITYA REDDY"
    "Reddy, Aditya"      -> "ADITYA REDDY"   (comma inversion)
    "  A.  Reddy "       -> "A REDDY"
    """
    s = unicodedata.normalize("NFKD", str(s)).strip()

    # "SURNAME, First Middle" -> "First Middle SURNAME". Only the FIRST comma is
    # structural (surname/given split); anything after it is folded in order.
    if "," in s:
        surname, _, rest = s.partition(",")
        if surname.strip() and rest.strip():
            s = f"{rest.strip()} {surname.strip()}"
        else:
            s = s.replace(",", " ")

    # Strip a leading honorific. Loop so "Dr. Shri X" collapses fully.
    prev = None
    while prev != s:
        prev = s
        s = HON.sub("", s.strip())

    s = re.sub(r"[^A-Za-z ]", " ", s)          # drop digits/punctuation/initials-dots
    return re.sub(r"\s+", " ", s).strip().upper()


def tokens(s: str) -> list[str]:
    """Normalised name -> token list. [] for an empty/blank name."""
    n = normalize(s)
    return n.split() if n else []


def surname(s: str) -> str:
    """Last token of the normalised name. '' when there is none."""
    t = tokens(s)
    return t[-1] if t else ""


def first_initial(s: str) -> str:
    """First character of the first token. '' when there is none."""
    t = tokens(s)
    return t[0][0] if t and t[0] else ""
