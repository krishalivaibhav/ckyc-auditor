"""MCA (Ministry of Corporate Affairs, India) anchor lookup.

The government-verified anchor is the whole point of this service: a DIN
(Director Identification Number) or CIN (Corporate Identification Number)
resolves to a real registered person/company with a known DOB and
nationality. We cross-check that against a name-match candidate so that a
same-name-different-person hit can be rejected.

Two implementations, selected by env var MCA_MODE (mock | real):
  - MockMCAClient : reads from a local fixture map. Use for build + demo.
  - RealMCAClient : hits mca.gov.in master data. Wire in later; the rest of
    the service does not change when you swap it in.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mca_master_data.json"


@dataclass
class MCARecord:
    """A government-verified master-data record for a DIN or CIN."""
    id: str                       # the DIN or CIN itself
    name: str                     # registered name
    dob: str | None = None        # YYYY-MM-DD (directors)
    nationality: str | None = None  # ISO-3166 alpha-2
    kind: str = "DIN"             # "DIN" or "CIN"


class MCAClient:
    """Interface. Returns an MCARecord or None if the id can't be resolved."""

    def lookup(self, din_or_cin: str) -> MCARecord | None:  # pragma: no cover
        raise NotImplementedError


class MockMCAClient(MCAClient):
    """Resolves against a local fixture map — no network, always available."""

    def __init__(self, fixture_path: Path = _FIXTURE_PATH) -> None:
        self._data: dict[str, dict] = {}
        if fixture_path.exists():
            self._data = json.loads(fixture_path.read_text())

    def lookup(self, din_or_cin: str) -> MCARecord | None:
        if not din_or_cin:
            return None
        rec = self._data.get(din_or_cin.strip().upper())
        if not rec:
            return None
        return MCARecord(
            id=din_or_cin.strip().upper(),
            name=rec.get("name", ""),
            dob=rec.get("dob"),
            nationality=rec.get("nationality"),
            kind=rec.get("kind", "CIN" if _looks_like_cin(din_or_cin) else "DIN"),
        )


class RealMCAClient(MCAClient):
    """Hits mca.gov.in basic master data. Placeholder wiring — the endpoint
    shape at mca.gov.in changes and often needs scraping, so treat any failure
    as 'unresolved' (returns None) rather than raising. The service then routes
    to needs_review, which is the safe default."""

    def __init__(self, base_url: str | None = None, timeout: float = 8.0) -> None:
        self._base = base_url or os.getenv("MCA_BASE_URL", "https://www.mca.gov.in")
        self._timeout = timeout

    def lookup(self, din_or_cin: str) -> MCARecord | None:
        if not din_or_cin:
            return None
        try:
            # NOTE: mca.gov.in has no clean public JSON API for master data.
            # This is intentionally a best-effort stub; on any failure we
            # return None so the resolver falls back to needs_review.
            resp = httpx.get(
                f"{self._base}/mcafoportal/companyMasterData.do",
                params={"id": din_or_cin.strip().upper()},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return MCARecord(
                id=din_or_cin.strip().upper(),
                name=data.get("name", ""),
                dob=data.get("dob"),
                nationality=data.get("nationality"),
                kind="CIN" if _looks_like_cin(din_or_cin) else "DIN",
            )
        except Exception:
            return None


def _looks_like_cin(value: str) -> bool:
    """CINs are 21 alphanumeric chars; DINs are 8 digits."""
    v = (value or "").strip()
    return len(v) > 8 and any(c.isalpha() for c in v)


def get_mca_client() -> MCAClient:
    """Factory — chooses implementation from MCA_MODE (default: mock)."""
    mode = os.getenv("MCA_MODE", "mock").strip().lower()
    return RealMCAClient() if mode == "real" else MockMCAClient()
