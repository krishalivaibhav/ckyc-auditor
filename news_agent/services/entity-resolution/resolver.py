"""Verdict decision logic — the heart of the service.

Turns each candidate match into a ResolutionVerdict. The governing rule:
name similarity is NEVER sufficient on its own. A government-verified MCA
DIN/CIN anchor either confirms a hit (DOB + nationality corroborate) or kills
it (they contradict). With no anchor, we route to needs_review — never to
confirmed_match — no matter how high the name score is.
"""

from __future__ import annotations

from datetime import datetime, timezone

from mca import MCAClient, MCARecord, get_mca_client
from models import Candidate, Entity, ResolutionVerdict
from scoring import best_name_score

# Thresholds — deliberately explicit so a reviewer can see the policy.
NAME_STRONG = 0.85     # clearly the same name
NAME_WEAK = 0.55       # below this, the name barely matches at all


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _field(raw: dict, *keys: str):
    """Fetch a candidate raw field, tolerant of key casing/aliases."""
    for k in keys:
        for cand in (k, k.lower(), k.upper(), k.capitalize()):
            if cand in raw and raw[cand] not in (None, ""):
                return raw[cand]
    return None


def resolve_candidate(entity: Entity, candidate: Candidate,
                      mca: MCAClient | None = None) -> ResolutionVerdict:
    """Resolve a single candidate against the entity into a verdict."""
    mca = mca or get_mca_client()

    name_score = best_name_score(candidate.matched_name, entity.name, entity.aliases)
    src = candidate.source_list or "the sanctions list"

    # ── Anchor lookup ────────────────────────────────────────────────────────
    record: MCARecord | None = None
    anchor_used = "none"
    if entity.din_or_cin:
        record = mca.lookup(entity.din_or_cin)
        if record is not None:
            anchor_used = record.kind  # "DIN" or "CIN"

    cand_dob = _field(candidate.raw, "dob", "date_of_birth", "birth_date")
    cand_nat = _field(candidate.raw, "nationality", "country", "citizenship")

    # ── Case A: anchor resolved — the decisive path ──────────────────────────
    if record is not None:
        dob_known = record.dob is not None and cand_dob is not None
        nat_known = record.nationality is not None and cand_nat is not None
        dob_match = dob_known and str(record.dob) == str(cand_dob)
        nat_match = nat_known and str(record.nationality).upper() == str(cand_nat).upper()
        dob_conflict = dob_known and not dob_match
        nat_conflict = nat_known and not nat_match

        if dob_conflict or nat_conflict:
            # Same name, different person — the anchor kills the hit.
            mism = []
            if dob_conflict:
                mism.append(f"DOB {record.dob} (verified) ≠ {cand_dob} (list entry)")
            if nat_conflict:
                mism.append(f"nationality {record.nationality} ≠ {cand_nat}")
            explanation = (
                f"Name matches {src} entry '{candidate.matched_name}' at "
                f"{_pct(name_score)}, but {entity.din_or_cin} "
                f"({anchor_used}) resolves to a different individual — "
                f"{'; '.join(mism)}. Treated as false positive."
            )
            return _verdict(entity, candidate, "false_positive",
                            confidence=0.9, explanation=explanation,
                            anchor_used=anchor_used)

        if (dob_match or nat_match) and name_score >= NAME_WEAK:
            corr = []
            if dob_match:
                corr.append(f"DOB {record.dob}")
            if nat_match:
                corr.append(f"nationality {record.nationality}")
            explanation = (
                f"Name matches {src} entry at {_pct(name_score)} and "
                f"{entity.din_or_cin} ({anchor_used}) confirms "
                f"{' and '.join(corr)}. Confirmed match."
            )
            confidence = round(min(0.99, 0.6 + 0.4 * name_score), 4)
            return _verdict(entity, candidate, "confirmed_match",
                            confidence=confidence, explanation=explanation,
                            anchor_used=anchor_used)

        # Anchor resolved but no corroborating fields to compare — can't confirm.
        explanation = (
            f"Name matches {src} entry at {_pct(name_score)} and "
            f"{entity.din_or_cin} ({anchor_used}) resolves, but no DOB/"
            f"nationality overlap was available to corroborate. Routed to "
            f"human review."
        )
        return _verdict(entity, candidate, "needs_review",
                        confidence=round(0.5 * name_score, 4),
                        explanation=explanation, anchor_used=anchor_used)

    # ── Case B: no anchor available ──────────────────────────────────────────
    # A name-only match must NEVER be confirmed. Very weak names with nothing
    # else going for them are false positives; everything else is needs_review.
    if name_score < NAME_WEAK:
        explanation = (
            f"Only a weak name similarity ({_pct(name_score)}) to {src} entry "
            f"'{candidate.matched_name}' and no verifying identifier. "
            f"Treated as false positive."
        )
        return _verdict(entity, candidate, "false_positive",
                        confidence=round(1 - name_score, 4),
                        explanation=explanation, anchor_used="none")

    reason = ("no DIN/CIN was provided" if not entity.din_or_cin
              else f"{entity.din_or_cin} could not be resolved in MCA master data")
    explanation = (
        f"Name matches {src} entry '{candidate.matched_name}' at "
        f"{_pct(name_score)}, but {reason}, so the match cannot be confirmed "
        f"against a government-verified anchor. Routed to human review."
    )
    return _verdict(entity, candidate, "needs_review",
                    confidence=round(0.5 * name_score, 4),
                    explanation=explanation, anchor_used="none")


def _verdict(entity: Entity, candidate: Candidate, verdict: str,
             confidence: float, explanation: str, anchor_used: str) -> ResolutionVerdict:
    return ResolutionVerdict(
        query_entity_id=entity.entity_id,
        candidate_id=candidate.candidate_id,
        verdict=verdict,
        confidence=confidence,
        explanation=explanation,
        anchor_used=anchor_used,
        resolved_at=_now_iso(),
    )
