"""MOHITA. 3 real lists -> canonical WatchlistEntry. See docs/02_MOHITA_watchlist.md."""
from contracts.models import WatchlistEntry

PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "HUF", "F": "Firm", "T": "Trust"}


def classify_alias(a: str) -> str:
    """CRITICAL. 97 of 227 UAPA aliases are bare tokens ('Salim', 'Amir Khan').
    If you mislabel these, Vaibhav's alias gate cannot work."""
    raise NotImplementedError("-> full_name | org_acronym | bare_token")


def load_all() -> list[WatchlistEntry]:
    raise NotImplementedError("nse_debarred + sabha_pep/rca + mha_uapa")
