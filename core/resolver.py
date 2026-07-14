"""VAIBHAV. The ER ladder. Rungs 0-7. See docs/01_VAIBHAV_core.md."""
from contracts.models import Candidate, Customer, WatchlistEntry

PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "HUF", "F": "Firm", "T": "Trust"}


def resolve(cust: Customer, cands: list[WatchlistEntry]) -> list[Candidate]:
    raise NotImplementedError("Rung 0 blocking -> 1 PAN exact -> 2 type gate -> 3 PAN mismatch "
                              "-> 4 alias gate -> 5 cross-list no-link -> 6 phonetic/fuzzy "
                              "-> 7 LLM adjudicator (ambiguous band only)")
