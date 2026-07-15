"""VAIBHAV. The ER ladder — Rungs 0-3 (this session).

    INPUT:  a Customer + the WatchlistEntry candidates from the blocking index (Rung 0)
    OUTPUT: one Candidate per meaningful (customer x entry) pair, each CONFIRMED
            or REJECTED, and every REJECT carrying a human-readable rejection_reason.

Rungs implemented here — all deterministic, no scoring, no fuzzy, no LLM:

    Rung 1  PAN exact                    -> CONFIRMED            confidence 1.0
    Rung 2  PAN 4th-char type gate       -> TYPE_MISMATCH_REJECT
    Rung 3  PAN present on both, differ  -> PAN_MISMATCH_REJECT
    (+)     name matches, PAN uncomparable-> NAME_EXACT CONFIRMED (provisional)

The REJECTED candidates are the product: they populate the suppression log.

Rungs 4-7 (alias-quality gate, cross-list no-link, phonetic/fuzzy, LLM
adjudicator) are later sessions. Until they land, a plain NAME_EXACT match is
surfaced (not suppressed) so recall on the no-PAN lists is preserved.
"""
from contracts.models import Candidate, Customer, WatchlistEntry
from core.normalize import normalize

# PAN 4th char encodes the holder type. Individual customer vs a "C" PAN on the
# watchlist -> different KIND of entity -> cannot be the same one.
PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "HUF", "F": "Firm", "T": "Trust",
            "A": "AOP", "B": "BOI", "G": "Government", "J": "Artificial Juridical", "L": "Local"}


def _name_match(cust_norm: str, entry: WatchlistEntry) -> tuple[bool, str]:
    """Exact normalised-name equality against the canonical name or any alias.
    Returns (matched, the_string_it_matched_on)."""
    if cust_norm and normalize(entry.name) == cust_norm:
        return True, entry.name
    for a in entry.aliases:
        if cust_norm and normalize(a) == cust_norm:
            return True, a
    return False, ""


def resolve(cust: Customer, cands: list[WatchlistEntry]) -> list[Candidate]:
    cust_pan = (cust.pan or "").strip().upper() or None
    cust_norm = normalize(cust.client_name)
    out: list[Candidate] = []

    for k, e in enumerate(cands):
        cid = f"CAND-{cust.client_id}-{k}"
        entry_pan = (e.pan or "").strip().upper() or None
        matched, matched_on = _name_match(cust_norm, e)

        # ---- Rung 1: PAN exact. A shared PAN is a confirmed match even when the
        # recorded name is noised — this is where noise-broken TPs come back.
        if cust_pan and entry_pan and cust_pan == entry_pan:
            out.append(Candidate(
                candidate_id=cid, client_id=cust.client_id, watchlist_id=e.watchlist_id,
                match_method="PAN_EXACT", confidence=1.0, decision="CONFIRMED",
                features={"pan_match": True, "customer_pan": cust_pan,
                          "name_similarity": 1.0 if matched else None,
                          "list": e.list, "list_status": e.status}))
            continue

        # PAN-based REJECTS only make sense when the NAME already collides —
        # otherwise blocking merely surfaced a phonetic near-miss we say nothing
        # about at this rung. Same name + PAN evidence = a real suppression.
        if matched and cust_pan and entry_pan:  # both PANs present, and they differ
            cust_type = cust.client_type
            entry_type = PAN_TYPE.get(entry_pan[3], "?")

            # ---- Rung 2: type gate. Different KIND of entity -> reject.
            if entry_type != cust_type:
                out.append(Candidate(
                    candidate_id=cid, client_id=cust.client_id, watchlist_id=e.watchlist_id,
                    match_method="TYPE_MISMATCH_REJECT", confidence=0.0, decision="REJECTED",
                    rejection_reason=(f"Name matches but PAN {entry_pan} is a {entry_type} "
                                      f"({entry_pan[3]}); customer is {cust_type} "
                                      f"-> cannot be the same entity"),
                    features={"customer_pan": cust_pan, "watchlist_pan": entry_pan,
                              "customer_type": cust_type, "watchlist_pan_type": entry_type,
                              "matched_on": matched_on,
                              "list": e.list, "list_status": e.status}))
                continue

            # ---- Rung 3: same type, different PAN -> different person. Full stop.
            out.append(Candidate(
                candidate_id=cid, client_id=cust.client_id, watchlist_id=e.watchlist_id,
                match_method="PAN_MISMATCH_REJECT", confidence=0.0, decision="REJECTED",
                rejection_reason=(f"PAN {cust_pan} != {entry_pan} -> distinct entities "
                                  f"despite identical name"),
                features={"customer_pan": cust_pan, "watchlist_pan": entry_pan,
                          "name_similarity": 1.0, "matched_on": matched_on,
                          "list": e.list, "list_status": e.status}))
            continue

        # ---- (+) Name matches but PAN can't adjudicate (one side has no PAN:
        # the PEP/RCA/UAPA lists carry none). Surfaced provisionally; the
        # alias-quality / cross-list / fuzzy rungs refine this later.
        if matched:
            out.append(Candidate(
                candidate_id=cid, client_id=cust.client_id, watchlist_id=e.watchlist_id,
                match_method="NAME_EXACT", confidence=0.7, decision="CONFIRMED",
                features={"name_similarity": 1.0, "matched_on": matched_on,
                          "list": e.list, "list_status": e.status,
                          "pan_comparable": bool(cust_pan and entry_pan),
                          "note": "no PAN on one side; provisional pending later rungs"}))
            continue

        # phonetic-only blocking collision, no name equality, no PAN evidence ->
        # nothing to assert at Rungs 0-3. (Handled by the fuzzy rung, later.)

    return out
