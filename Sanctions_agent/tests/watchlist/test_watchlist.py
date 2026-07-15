from datetime import date

from contracts.models import WatchlistEntry
from watchlist.index import ScreeningIndex, normalize_name
from watchlist.load import classify_alias


def test_normalization_inverts_comma_name_and_drops_title():
    assert normalize_name("Dr. Khan, Amir") == "amir khan"


def test_alias_quality_protects_ambiguous_uapa_aliases():
    assert classify_alias("Amir Khan") == "bare_token"
    assert classify_alias("PREPAK") == "org_acronym"
    assert classify_alias("Hafiz Muhammad Saeed") == "full_name"


def test_index_uses_pan_and_does_not_expand_bare_aliases():
    entry = WatchlistEntry(
        watchlist_id="mha-1", list="MHA_UAPA", entity_type="Individual", name="Ashiq Ahmed",
        aliases=["Nengroo"], alias_quality={"Nengroo": "bare_token"}, source_url=["https://example.test"],
    )
    nse = WatchlistEntry(
        watchlist_id="nse-1", list="NSE_SEBI_DEBARRED", entity_type="Individual", name="Asha Kumar",
        pan="ABCDE1234P", status="active", source_url=["https://example.test"], order_date=date(2024, 1, 1),
    )
    index = ScreeningIndex([entry, nse])
    assert index.candidates("Nengroo") == []
    assert index.candidates("unrelated", "ABCDE1234P") == [nse]
