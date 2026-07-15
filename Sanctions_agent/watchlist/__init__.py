"""Mohita's canonical regulatory watchlist package."""

from watchlist.index import ScreeningIndex
from watchlist.load import load_watchlist, relatives
from watchlist.replay import replay

# This is deliberately the complete cross-package surface.  Candidate counts are simply
# ``len(index.candidates(name, pan))``; no bespoke dictionary crosses the boundary.
__all__ = ["ScreeningIndex", "load_watchlist", "relatives", "replay"]
