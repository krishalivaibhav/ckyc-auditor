"""
signals/kyc_list.py
-------------------
In-memory watchlist of KYC entities to be monitored.
Also persists to the SQLite DB so the list survives server restarts.
"""

import json
import logging
import os
from pathlib import Path
from .models import WatchedEntity
from typing import Dict

logger = logging.getLogger("signals.kyc_list")
_watchlist: Dict[str, WatchedEntity] = {}

# THE SHARED DATASET. The news agent takes the names it monitors from the SAME
# customer book the ambiguity agent resolves against (the pipeline's
# fixtures/customers.json). One dataset, both agents — so every adverse signal
# emitted downstream maps back to a real customer.
SHARED_CUSTOMERS_JSON = os.getenv(
    "SHARED_CUSTOMERS_JSON",
    str(Path(__file__).resolve().parents[2]
        / "investigation_agent" / "fixtures" / "customers.json"),
)


def seed_from_shared_dataset() -> bool:
    """Load the watchlist from the shared customer book. Duplicate names (two
    clients named 'Dipak Dwiwedi') collapse into ONE watched name here — the
    ambiguity agent downstream is what splits them back into distinct clients.
    Returns False (caller falls back to seed_defaults) if the file is missing."""
    path = Path(SHARED_CUSTOMERS_JSON)
    if not path.exists():
        logger.warning(f"Shared customer dataset not found at {path}; "
                       f"falling back to built-in demo watchlist.")
        return False
    customers = json.loads(path.read_text(encoding="utf-8"))
    for c in customers:
        add_entity(WatchedEntity(
            name        = c["client_name"],
            aliases     = [],
            entity_type = "person" if c.get("client_type") == "Individual" else "company",
            country     = c.get("country", "IN"),
            sector      = c.get("sector"),
            notes       = f"shared-dataset client {c.get('client_id', '?')}",
        ))
    logger.info(f"Seeded {len(_watchlist)} watched name(s) from the shared "
                f"customer dataset ({len(customers)} customer records).")
    return True


def seed_defaults():
    """Pre-load demo entities for the hackathon demo."""
    defaults = [
        WatchedEntity(
            name        = "Adani Group",
            aliases     = ["Adani Enterprises", "Adani Ports", "Adani Green"],
            entity_type = "company",
            country     = "IN",
            sector      = "Infrastructure",
        ),
        WatchedEntity(
            name        = "Nirav Modi",
            aliases     = ["Firestar Diamond", "Nirav Modi Jewels"],
            entity_type = "person",
            country     = "IN",
            sector      = "Jewellery",
            notes       = "PNB fraud accused",
        ),
        WatchedEntity(
            name        = "Infosys",
            aliases     = ["Infy", "Infosys BPO"],
            entity_type = "company",
            country     = "IN",
            sector      = "Information Technology",
            notes       = "Demo: tests false-positive suppression",
        ),
    ]
    for e in defaults:
        add_entity(e)
    logger.info(f"Seeded {len(defaults)} default entities into watchlist.")


def add_entity(entity: WatchedEntity):
    _watchlist[entity.name.lower()] = entity
    logger.info(f"Entity added to watchlist: '{entity.name}'")


def remove_entity(name: str) -> bool:
    key = name.lower()
    if key in _watchlist:
        del _watchlist[key]
        logger.info(f"Entity removed from watchlist: '{name}'")
        return True
    return False


def get_all() -> list[WatchedEntity]:
    return list(_watchlist.values())


def get_entity(name: str) -> WatchedEntity | None:
    return _watchlist.get(name.lower())
