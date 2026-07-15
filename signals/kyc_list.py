"""
signals/kyc_list.py
-------------------
Manages the in-memory list of watched entities.

In production, this list would be seeded from the KYC customer database
(e.g. the Synthetic KYC CSV or a Postgres table managed by core/).
For now it is managed via API endpoints so the system can be demoed live.
"""

from .models import WatchedEntity
from typing import Dict

# ── In-memory store ─────────────────────────────────────────────────────────
# key = entity name (lower-cased)
_watchlist: Dict[str, WatchedEntity] = {}


def seed_defaults():
    """
    Pre-load a small set of demo entities so the agent has something to
    scan immediately on startup — useful for the hackathon demo.
    Replace or extend these with entries from the real KYC CSV.
    """
    defaults = [
        WatchedEntity(
            name="Adani Group",
            aliases=["Adani Enterprises", "Adani Ports"],
            entity_type="company",
            notes="High-profile Indian conglomerate",
        ),
        WatchedEntity(
            name="Nirav Modi",
            aliases=["Nirav Modi Jewels", "Firestar Diamond"],
            entity_type="person",
            notes="PNB fraud accused",
        ),
        WatchedEntity(
            name="Infosys",
            aliases=["Infy"],
            entity_type="company",
            notes="IT company — used in demo to test false-positive suppression",
        ),
    ]
    for entity in defaults:
        add_entity(entity)


def add_entity(entity: WatchedEntity):
    _watchlist[entity.name.lower()] = entity


def remove_entity(name: str) -> bool:
    key = name.lower()
    if key in _watchlist:
        del _watchlist[key]
        return True
    return False


def get_all() -> list[WatchedEntity]:
    return list(_watchlist.values())


def get_entity(name: str) -> WatchedEntity | None:
    return _watchlist.get(name.lower())
