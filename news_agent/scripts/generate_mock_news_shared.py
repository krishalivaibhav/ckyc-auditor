"""Generate data/mock_news.json for the SHARED customer dataset.

The original scripts/generate_mock_news.py reads data/clients_with_fatf_ofac.csv,
which is not in the repo — its output covered faker names that match neither the
news watchlist nor the pipeline's customer book, so nothing ever flowed end-to-end.

This generator writes mock articles for the names in the shared dataset
(investigation_agent/fixtures/customers.json — the same book the watchlist seeds
from and the ambiguity agent resolves against), so USE_MOCK_NEWS=true exercises
the FULL pipeline:

    adverse for the golden-tier customers  -> signal -> ingest -> case + SAR
    benign for the clean customers         -> triaged benign, nothing emitted
    (that suppression IS part of the demo: an agent that always finds
    something is the failure mode this system exists to avoid)

Descriptions deliberately name the designating authorities (NIA/MHA, SEBI/NSE,
Parliament) so the investigation agent's corroboration probes have something
real to find. Run:  python scripts/generate_mock_news_shared.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mock_news.json"

NOW = datetime.now(timezone.utc)


def _at(hours_ago: int) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


ARTICLES = [
    # ── Muhammad Saeed (C1007, golden CRITICAL — UAPA) ────────────────────────
    {
        "entity_name": "Muhammad Saeed",
        "title": "NIA widens terror financing probe; Muhammad Saeed among names under scrutiny",
        "description": ("The National Investigation Agency (NIA), acting on a Ministry of "
                        "Home Affairs UAPA notification, has widened its terror financing "
                        "probe. Investigators said Muhammad Saeed is among those being "
                        "examined for suspected cross-border transfers."),
        "source": "The Hindu", "hours_ago": 6, "slug": "nia-terror-probe-saeed",
    },
    {
        "entity_name": "Muhammad Saeed",
        "title": "Muhammad Saeed's counsel denies wrongdoing as agencies continue inquiry",
        "description": ("Counsel for Muhammad Saeed issued a statement denying all "
                        "allegations in the ongoing terror financing investigation and "
                        "said his client is cooperating with the NIA."),
        "source": "Hindustan Times", "hours_ago": 3, "slug": "saeed-counsel-denies",
    },
    # ── Dipak Dwiwedi (C1001 golden HIGH; C1002 same name, different PAN) ─────
    {
        "entity_name": "Dipak Dwiwedi",
        "title": "SEBI moves to debar Dipak Dwiwedi over commodity market manipulation",
        "description": ("The Securities and Exchange Board of India (SEBI) has issued an "
                        "order to debar Dipak Dwiwedi from the securities market following "
                        "an NSE surveillance report on suspected market manipulation in "
                        "commodity contracts."),
        "source": "Economic Times", "hours_ago": 12, "slug": "sebi-debar-dwiwedi",
    },
    {
        "entity_name": "Dipak Dwiwedi",
        "title": "Dipak Dwiwedi elected treasurer of Mumbai commodities trade association",
        "description": ("The Mumbai commodities trade association announced its new office "
                        "bearers this week. Dipak Dwiwedi was elected treasurer for a "
                        "two-year term."),
        "source": "Local Business Daily", "hours_ago": 40, "slug": "dwiwedi-treasurer",
    },
    # ── Sumalatha Ambareesh (C1005, golden EDD — PEP) ─────────────────────────
    {
        "entity_name": "Sumalatha Ambareesh",
        "title": "Anti-corruption panel summons questioned over alleged bribery in constituency works",
        "description": ("An anti-corruption panel has issued summons in a probe into alleged "
                        "bribery in constituency development works. Parliament records show "
                        "Sumalatha Ambareesh, a sitting member, has been asked to respond to "
                        "questions on undocumented payments."),
        "source": "Reuters", "hours_ago": 20, "slug": "ambareesh-bribery-probe",
    },
    # ── Amir Khan (C1003, golden NONE — the bare-alias name-collision story) ──
    {
        "entity_name": "Amir Khan",
        "title": "Amir Khan announces new film wrapping principal photography in Jaipur",
        "description": ("Actor Amir Khan told reporters his upcoming feature has wrapped "
                        "principal photography in Jaipur and is slated for a festival "
                        "premiere next spring."),
        "source": "NDTV", "hours_ago": 8, "slug": "amir-khan-film",
    },
    # ── Clean customers: benign coverage only (false-positive suppression) ────
    {
        "entity_name": "Tanvi Chatterjee",
        "title": "Tanvi Chatterjee appointed to fintech startup advisory board",
        "description": ("Fintech startup PayLeaf announced that Tanvi Chatterjee has been "
                        "appointed to its advisory board, citing her decade of experience "
                        "in retail payments."),
        "source": "Moneycontrol", "hours_ago": 15, "slug": "chatterjee-board",
    },
    {
        "entity_name": "INDRAWATI NIRMAN PVT LTD",
        "title": "Indrawati Nirman Pvt Ltd wins highway maintenance contract in Madhya Pradesh",
        "description": ("Indrawati Nirman Pvt Ltd said it has won a three-year highway "
                        "maintenance contract from the state public works department, its "
                        "largest order this fiscal year."),
        "source": "Business Standard", "hours_ago": 30, "slug": "indrawati-contract",
    },
]


def main() -> None:
    out = [{
        "entity_name": a["entity_name"],
        "title": a["title"],
        "description": a["description"],
        "url": f"https://mocknews.example/article/{a['slug']}",
        "source": {"name": a["source"]},
        "publishedAt": _at(a["hours_ago"]),
    } for a in ARTICLES]
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    names = sorted({a["entity_name"] for a in ARTICLES})
    print(f"Wrote {len(out)} mock article(s) for {len(names)} shared-dataset "
          f"name(s) -> {OUT}")
    for n in names:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
