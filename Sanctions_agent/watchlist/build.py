"""Compile the raw regulatory exports into reproducible watchlist artifacts.

Run with ``python -m watchlist.build``.  The generated JSON files are derived assets;
this module is the auditable location for every normalisation decision.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from contracts.models import WatchlistEntry
from watchlist.load import CANONICAL_PATH, DATA_DIR, DETAILS_PATH, PAN_TYPE, RELATIONSHIPS_PATH, classify_alias

NSE_PAGE = "https://www.nseindia.com/regulations/member-sebi-debarred-entities"
MHA_PAGE = "https://www.mha.gov.in/en/banned-organisations"
SABHA_PAGE = "https://sansad.in/"
REVOKED = re.compile(r"\brevok(?:ed|ation)\b", re.I)


def _values(record: dict[str, Any], key: str) -> list[Any]:
    value = record.get("properties", {}).get(key, [])
    return value if isinstance(value, list) else [value]


def _first(record: dict[str, Any], key: str, default: Any = None) -> Any:
    values = _values(record, key)
    return values[0] if values else default


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d-%b-%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _clean_pan(value: Any) -> str | None:
    value = str(value or "").strip().upper()
    return value if re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", value) else None


def _entity_type(pan: str | None, schema: str = "") -> str:
    if schema == "Organization":
        return "Organization"
    if pan and len(pan) == 10:
        return PAN_TYPE.get(pan[3], "Unknown")
    return "Individual" if schema == "Person" else "Unknown"


def _status(duration: str | None, end_date: date | None) -> str:
    return "revoked" if end_date or REVOKED.search(duration or "") else "active"


def _urls(values: Iterable[Any], fallback: str) -> list[str]:
    clean = [str(value) for value in values if isinstance(value, str) and value.startswith("http")]
    return list(dict.fromkeys(clean)) or [fallback]


def _order_id(order_text: str) -> str | None:
    normalized = " ".join((order_text or "").casefold().split())
    return f"NSE-{hashlib.sha256(normalized.encode()).hexdigest()[:16]}" if normalized else None


def _stock_orders(record: dict[str, Any]) -> list[dict[str, Any]]:
    orders = []
    for sanction in _values(record, "sanctions"):
        props = sanction.get("properties", {})
        duration = (props.get("duration") or [None])[0]
        end_date = _parse_date((props.get("endDate") or [None])[0])
        description = (props.get("description") or [""])[0]
        orders.append({
            "sanction_id": sanction.get("id"), "order_date": str((props.get("date") or [None])[0] or "") or None,
            "end_date": end_date.isoformat() if end_date else None, "duration": duration,
            "status": _status(duration, end_date), "order_particulars": description,
            "order_id": _order_id(description), "source_urls": _urls(props.get("sourceUrl", []), NSE_PAGE),
            "authority": (props.get("authority") or [None])[0],
        })
    return orders


def _stock_entries(path: Path) -> tuple[list[WatchlistEntry], dict[str, dict]]:
    entries, details = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        pan = _clean_pan(_first(record, "taxNumber"))
        names = [str(value).strip() for value in _values(record, "name") if str(value).strip()]
        canonical = names[0] if names else record.get("caption", record["id"])
        orders = _stock_orders(record)
        active = [order for order in orders if order["status"] == "active"]
        selected = max(active or orders, key=lambda item: item.get("order_date") or "", default={})
        urls = _urls([url for order in orders for url in order["source_urls"]], NSE_PAGE)
        entry = WatchlistEntry(
            watchlist_id=record["id"], list="NSE_SEBI_DEBARRED", entity_type=_entity_type(pan, record.get("schema", "")),
            name=canonical, aliases=list(dict.fromkeys(names[1:])), pan=pan,
            status="active" if active else "revoked", order_id=selected.get("order_id"),
            order_date=_parse_date(selected.get("order_date")), source_url=urls,
            first_seen=_parse_datetime(record.get("first_seen")), last_change=_parse_datetime(record.get("last_change")),
        )
        entries.append(entry)
        details[entry.watchlist_id] = {
            "canonical_name": canonical, "source": "NSE/SEBI OpenSanctions", "source_urls": urls,
            "all_names": names, "pan": pan, "registration_numbers": _values(record, "registrationNumber"),
            "addresses": _values(record, "address"), "ownership_assets": _values(record, "ownershipAsset"),
            "ownership_owners": _values(record, "ownershipOwner"), "orders": orders,
            "first_seen": record.get("first_seen"), "last_seen": record.get("last_seen"),
            "last_change": record.get("last_change"),
        }
    return entries, details


def _sabha_entries(path: Path) -> tuple[list[WatchlistEntry], dict[str, dict], dict[str, list[dict]]]:
    entries, details, relationships = [], {}, defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        topics = set(str(value) for value in _values(record, "topics"))
        if "role.pep" in topics:
            statuses = [str(value) for value in _values(record, "status")]
            list_name, status = ("SABHA_PEP_CURRENT", "current") if any("sitting" in value.casefold() for value in statuses) else ("SABHA_PEP_FORMER", "former")
        elif "role.rca" in topics:
            list_name, status = "SABHA_RCA", "former"
        else:
            continue
        names = [str(value).strip() for value in _values(record, "name") if str(value).strip()]
        canonical = names[0] if names else record.get("caption", record["id"])
        dob = _parse_date(_first(record, "birthDate"))
        entry = WatchlistEntry(
            watchlist_id=record["id"], list=list_name, entity_type="Individual", name=canonical,
            aliases=list(dict.fromkeys(names[1:])), dob=dob, party=_first(record, "political"), status=status,
            source_url=[SABHA_PAGE], first_seen=_parse_datetime(record.get("first_seen")),
            last_change=_parse_datetime(record.get("last_change")),
        )
        entries.append(entry)
        details[entry.watchlist_id] = {
            "canonical_name": canonical, "source": "India Lok and Rajya Sabha Members", "source_urls": [SABHA_PAGE],
            "all_names": names, "first_name": _values(record, "firstName"), "last_name": _values(record, "lastName"),
            "title": _values(record, "title"), "dob": dob.isoformat() if dob else None,
            "birth_place": _values(record, "birthPlace"), "gender": _values(record, "gender"),
            "citizenship": _values(record, "citizenship"), "addresses": _values(record, "address"),
            "emails": _values(record, "email"), "party": _values(record, "political"), "status": _values(record, "status"),
            "positions": _values(record, "positionOccupancies"), "education": _values(record, "education"),
            "notes": _values(record, "notes"), "first_seen": record.get("first_seen"), "last_seen": record.get("last_seen"),
            "last_change": record.get("last_change"),
        }
        for link in [*_values(record, "familyRelative"), *_values(record, "familyPerson")]:
            props = link.get("properties", {}) if isinstance(link, dict) else {}
            relation = (props.get("relationship") or ["associate"])[0]
            other = (props.get("person") or props.get("relative") or [None])[0]
            if isinstance(other, dict) and other.get("id"):
                item = {"watchlist_id": other["id"], "relationship": relation, "name": other.get("caption")}
                relationships[entry.watchlist_id].append(item)
                relationships[other["id"]].append({"watchlist_id": entry.watchlist_id, "relationship": relation, "name": canonical})
    return entries, details, relationships


def _mha_entries(path: Path) -> tuple[list[WatchlistEntry], dict[str, dict]]:
    entries, details = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        names = [str(value).strip() for value in _values(record, "name") if str(value).strip()]
        canonical = names[0] if names else record.get("caption", record["id"])
        aliases = list(dict.fromkeys([*names[1:], *[str(value).strip() for value in _values(record, "alias") if str(value).strip()]]))
        alias_quality = {alias: classify_alias(alias) for alias in aliases}
        urls = _urls(_values(record, "sourceUrl"), MHA_PAGE)
        entry = WatchlistEntry(
            watchlist_id=record["id"], list="MHA_UAPA", entity_type=_entity_type(None, record.get("schema", "")),
            name=canonical, aliases=aliases, alias_quality=alias_quality, status="active", source_url=urls,
            first_seen=_parse_datetime(record.get("first_seen")), last_change=_parse_datetime(record.get("last_change")),
        )
        entries.append(entry)
        sanctions = [item.get("properties", {}) for item in _values(record, "sanctions") if isinstance(item, dict)]
        details[entry.watchlist_id] = {
            "canonical_name": canonical, "source": "Ministry of Home Affairs UAPA", "source_urls": urls,
            "entity_schema": record.get("schema"), "all_names": names, "aliases": alias_quality,
            "program_ids": _values(record, "programId"), "designations": sanctions,
            "links_from": _values(record, "unknownLinkFrom"), "links_to": _values(record, "unknownLinkTo"),
            "first_seen": record.get("first_seen"), "last_seen": record.get("last_seen"), "last_change": record.get("last_change"),
        }
    return entries, details


def _raw_nse_details(paths: list[Path], entries: list[WatchlistEntry], details: dict[str, dict]) -> None:
    """Join the two raw NSE workbooks by PAN, preserving their DIN/CIN and circular detail."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - documents the install prerequisite
        raise RuntimeError("pandas and xlrd are required; install requirements.txt") from exc
    by_pan = {entry.pan: entry.watchlist_id for entry in entries if entry.pan}
    for path in paths:
        frame = pd.read_excel(path, dtype=str).fillna("")
        for row in frame.to_dict(orient="records"):
            pan = _clean_pan(row.get("PAN"))
            if not pan:
                continue
            watchlist_id = by_pan.get(pan)
            if not watchlist_id:
                # A raw source-only record still deserves a canonical entry.
                name = str(row.get("Entity / Individual Name", "")).strip() or pan
                order_text = str(row.get("Order Particulars", "")).strip()
                duration = str(row.get("Period", "")).strip()
                end_date = _parse_date(row.get("Date of NSE circular. (For Revocation)")) if REVOKED.search(duration) else None
                watchlist_id = f"NSE-RAW-{pan}"
                entries.append(WatchlistEntry(
                    watchlist_id=watchlist_id, list="NSE_SEBI_DEBARRED", entity_type=_entity_type(pan), name=name,
                    pan=pan, status=_status(duration, end_date), order_id=_order_id(order_text),
                    order_date=_parse_date(row.get("Order Date")), source_url=[NSE_PAGE],
                ))
                details[watchlist_id] = {"canonical_name": name, "source": "NSE raw workbook", "source_urls": [NSE_PAGE], "orders": []}
                by_pan[pan] = watchlist_id
            details[watchlist_id].setdefault("raw_nse_rows", []).append({key: str(value) for key, value in row.items() if str(value)})


def build_watchlist(data_dir: Path = DATA_DIR) -> list[WatchlistEntry]:
    """Build all artifacts and return the canonical reference list."""
    stock, stock_details = _stock_entries(data_dir / "targets_nested_stock_.json")
    sabha, sabha_details, relationships = _sabha_entries(data_dir / "targets_nested_sabha_.json")
    mha, mha_details = _mha_entries(data_dir / "targets_nested_mha_.json")
    entries = [*stock, *sabha, *mha]
    details = {**stock_details, **sabha_details, **mha_details}
    _raw_nse_details([data_dir / "sebi_stock_.xls", data_dir / "other_stock_.xlsx"], entries, details)

    CANONICAL_PATH.write_text(json.dumps([entry.model_dump(mode="json") for entry in entries], ensure_ascii=False), encoding="utf-8")
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    RELATIONSHIPS_PATH.write_text(json.dumps(relationships, ensure_ascii=False), encoding="utf-8")
    return entries


if __name__ == "__main__":
    result = build_watchlist()
    print(f"Built {len(result):,} canonical watchlist entries -> {CANONICAL_PATH}")
