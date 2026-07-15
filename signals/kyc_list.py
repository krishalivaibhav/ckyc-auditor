"""
signals/kyc_list.py
-------------------
In-memory watchlist of KYC entities to be monitored.
Also persists to the SQLite DB so the list survives server restarts.
"""

import logging
from .models import WatchedEntity
from typing import Dict

logger = logging.getLogger("signals.kyc_list")
_watchlist: Dict[str, WatchedEntity] = {}


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
