"""VAIBHAV. The direct in-memory pipeline.

Components hand off `contracts/models.py` objects via DIRECT FUNCTION CALLS — no
database between stages, no message bus. The DB is a sink at the very end.

    Customer
       │
       ▼   load_watchlist()            -> list[WatchlistEntry]   (Mohita)
           fetch_and_triage(customer)  -> list[Signal]           (Aditya, network)
       ▼   resolve(customer, watchlist)-> list[Candidate]        (core / this file's dep)
           assess(candidates, signals) -> RiskAssessment         (core / scoring, later)
       ▼   (only if tier != NONE)
           investigate(assessment)     -> list[Evidence]         (Sneha)
           draft_sar(assessment, ev)   -> SAR                    (Sneha)
       ▼   persist: Case + SAR + AuditEvent  -> SQLite  (the ONLY DB writes)

Two guarantees make this safe to run before the other four packages exist:
  1. Every hand-off is a typed contract object — never a dict, never an ad-hoc
     shape. Removing the DB makes the contract MORE load-bearing, not less.
  2. Each stage is wrapped in `safe()` so a failure DEGRADES (empty result) rather
     than crashing the run. Matters most for `fetch_and_triage` (touches GDELT).

Stages whose owner hasn't shipped yet are backed by `fixtures/` here, so the whole
pipeline runs end-to-end TODAY. Each stub is a seam: when an owner ships their real
function to the documented signature, swap the import — nothing else changes.
"""
import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from uuid import uuid4

from contracts.models import (AuditEvent, Case, Customer, Evidence, RiskAssessment,
                              SAR, Signal, TimelineEvent, WatchlistEntry)
from core.blocking import Blocker
from core.investigate import deterministic_adjudicator, investigate  # investigation agent
from core.resolver import resolve
from db.store import init_db, load_case, persist

log = logging.getLogger("ckyc.orchestrator")
FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _fx(name: str):
    return json.loads((FIX / f"{name}.json").read_text())


def safe(fn, *args, default=None, label=None):
    """Run a pipeline stage; on ANY failure log it and return `default`. One dead
    component must never kill the run (demo-day insurance for the network stage)."""
    try:
        return fn(*args)
    except Exception as e:   # noqa: BLE001 — deliberate: degrade, don't crash
        log.warning("stage %s failed (%s); degrading to %r",
                    label or getattr(fn, "__name__", "?"), e, default)
        return default


# ================================================================ component stages
# Fixture-backed stubs. Replace each with the owner's real function (same signature)
# when it ships — the orchestrator body below does not change.

def load_watchlist() -> list[WatchlistEntry]:                     # ---- Mohita
    return [WatchlistEntry(**w) for w in _fx("watchlist")]


def fetch_and_triage(customer: Customer) -> list[Signal]:        # ---- Aditya (network)
    """Adverse-media + watchlist-delta signals for this customer. Real impl hits
    GDELT/RSS — ALWAYS call via safe(default=[])."""
    first = (customer.client_name.split() or [""])[0].lower()
    sigs = [Signal(**s) for s in _fx("signals")]
    return [s for s in sigs if any(first and first in m.lower() for m in s.mentioned_names)]


def draft_sar(assessment: RiskAssessment, evidence: list[Evidence],
              customer: Customer) -> SAR:                          # ---- Sneha
    """Reuse a golden fixture SAR when it matches this subject, else synthesize a
    minimal one. (A real draft_sar takes (assessment, evidence); the customer is
    threaded here only because the stub has no customer lookup.)"""
    for s in _fx("sar"):
        if s.get("subject_pan") and s["subject_pan"] == (customer.pan or ""):
            return SAR(**s)
    return SAR(
        sar_id=f"SAR-{customer.client_id}", case_id=f"CASE-{customer.client_id}",
        drafted_at=assessment.assessed_at, subject_name=customer.client_name,
        subject_pan=customer.pan,
        sections={
            "subject_identification": f"{customer.client_name} "
                f"(PAN {customer.pan or 'not on file'}), a {customer.client_type} customer.",
            "basis_for_suspicion": assessment.explanation or "See risk assessment.",
            "risk_assessment": f"Tier {assessment.tier}. Gates: "
                f"{', '.join(assessment.gates_fired) or 'none'}.",
            "recommended_action": "Human sign-off required before filing.",
        },
        evidence=list(evidence),
        unverified_claims=[], citation_coverage=0.0, status="DRAFT")


# ================================================================ core stages
def _resolve_stage(customer: Customer, watchlist: list[WatchlistEntry]):
    """Rung 0 blocking + Rungs 1-3 resolution. Returns list[Candidate]."""
    if not watchlist:
        return []
    blocked = Blocker(watchlist).candidates(customer.client_name, customer.pan)
    return resolve(customer, blocked)


def _assess(customer: Customer, candidates, signals) -> RiskAssessment:
    """Delegate to core.scoring.assess when it lands; until then, fixture-backed
    stub. Scoring is a later session — this file does NOT implement it."""
    try:
        from core.scoring import assess as real_assess
        return real_assess(customer.client_id, candidates, signals, "NONE")
    except NotImplementedError:
        return _stub_assessment(customer, candidates, signals)


def _stub_assessment(customer: Customer, candidates, signals) -> RiskAssessment:
    """Golden fixture assessment for this client if present; otherwise a NONE-tier
    assessment that still records the ER suppressions (rejected candidates carry
    their reason — the product — even before scoring exists)."""
    for a in _fx("assessments"):
        if a["client_id"] == customer.client_id:
            return RiskAssessment(**a)
    supp = [f"{c.match_method}:{c.watchlist_id}"
            for c in candidates if c.decision == "REJECTED"]
    ts = datetime.combine(customer.last_kyc_refresh, time(9, 0), tzinfo=timezone.utc)
    return RiskAssessment(
        assessment_id=f"ASM-{customer.client_id}", client_id=customer.client_id,
        assessed_at=ts, prior_tier="NONE", tier="NONE", score=0.0,
        gates_fired=[], suppressions=supp,
        contributing_signals=[s.signal_id for s in signals],
        contributing_candidates=[c.candidate_id for c in candidates],
        evidence=[],
        explanation="No gate fired. Scoring is not yet wired (later session); "
                    "ER suppressions are recorded so the audit trail is complete.")


# ================================================================ assembly
def build_case(customer: Customer, assessment: RiskAssessment, sar: SAR | None) -> Case:
    ts = assessment.assessed_at
    if assessment.tier == "CRITICAL":
        status = "ESCALATED"
    elif assessment.tier == "NONE":
        status = "DISMISSED"
    else:
        status = "OPEN"

    timeline = [TimelineEvent(
        at=ts, kind="REASSESSMENT",
        summary=(assessment.explanation or "Reassessed.")[:200],
        evidence_ids=[e.evidence_id for e in assessment.evidence],
        tier_before=assessment.prior_tier, tier_after=assessment.tier)]
    if sar:
        timeline.append(TimelineEvent(
            at=ts, kind="SAR",
            summary=f"SAR drafted. Citation coverage {sar.citation_coverage:.0%}.",
            evidence_ids=[e.evidence_id for e in sar.evidence],
            tier_before=assessment.tier, tier_after=assessment.tier))

    return Case(
        case_id=f"CASE-{customer.client_id}", client_id=customer.client_id,
        opened_at=ts, status=status, tier=assessment.tier,
        assessment_ids=[assessment.assessment_id], timeline=timeline,
        sar=sar, reviewer_actions=[])


def _audit(action, obj_type, obj_id, ts, rationale, n, case_id):
    # audit_id must be unique per EMISSION (the table is append-only; re-running the
    # pipeline appends a fresh trail, never overwrites). uuid suffix guarantees that
    # while the case_id/n prefix keeps it human-readable and ordered.
    return AuditEvent(
        audit_id=f"AUD-{case_id}-{n}-{uuid4().hex[:8]}", at=ts, actor="agent:orchestrator",
        action=action, object_type=obj_type, object_id=obj_id, rationale=rationale)


# ================================================================ the pipeline
def _merge_with_prior(case: Case) -> Case:
    """Near-real-time ingest re-fires for the same customer as events land over
    time (a sanction is imposed, adverse media breaks, an order is revoked). The
    sink keys one Case per client (`INSERT OR REPLACE`), so without a merge every
    re-run would CLOBBER the accumulated history. Merge instead: union the
    timeline (deduped), keep the earliest opened_at, and preserve reviewer
    actions. Everything else (tier, status, sar, assessment ids) reflects the
    LATEST run — the current truth."""
    try:
        prior = load_case(case.case_id)
    except Exception:   # noqa: BLE001 — sink not initialised yet: nothing to merge
        prior = None
    if not prior:
        return case

    def _key(at, kind, summary):
        return (str(at)[:19], kind, summary)   # second precision is plenty for dedup

    seen = {_key(t.at.isoformat(), t.kind, t.summary) for t in case.timeline}
    merged = list(case.timeline)
    for t in prior.get("timeline", []):
        if _key(t["at"], t["kind"], t["summary"]) not in seen:
            merged.append(TimelineEvent(**t))
    merged.sort(key=lambda t: t.at)

    from contracts.models import ReviewerAction
    actions = [ReviewerAction(**r) for r in prior.get("reviewer_actions", [])]
    opened = min(case.opened_at,
                 datetime.fromisoformat(prior["opened_at"]))
    return case.model_copy(update={
        "timeline": merged, "opened_at": opened,
        "reviewer_actions": actions or case.reviewer_actions})


def run_pipeline(customer: Customer, persist_result: bool = True,
                 use_llm: bool = True,
                 external_signals: list[Signal] | None = None,
                 extra_watchlist: list[WatchlistEntry] | None = None) -> Case:
    """Run one customer through the full pipeline and return the resulting Case.
    With persist_result=True (default), writes Case + SAR + AuditEvents to SQLite.

    use_llm controls the investigation stage's reasoning step: True (interactive
    default, e.g. POST /api/pipeline) allows live Anthropic adjudication when a key
    is set; False forces the deterministic adjudicator — used by startup seeding so
    boot makes ZERO API calls even with a key present.

    external_signals / extra_watchlist are the NEAR-REAL-TIME ingest seam: the
    sanctions monitor sends the watchlist entries it matched (extra_watchlist) and
    the news agent sends adverse-media Signals (external_signals). Both are unioned
    with the pipeline's own reference data so resolve/investigate see them, each
    external signal lands on the Case timeline as a SIGNAL event, and re-runs MERGE
    into the persisted case instead of clobbering its history."""
    watchlist = safe(load_watchlist, default=[], label="load_watchlist")
    if extra_watchlist:
        known = {e.watchlist_id for e in watchlist}
        watchlist = watchlist + [e for e in extra_watchlist if e.watchlist_id not in known]
    signals = safe(fetch_and_triage, customer, default=[], label="fetch_and_triage")
    if external_signals:
        known_sig = {s.signal_id for s in signals}
        signals = signals + [s for s in external_signals if s.signal_id not in known_sig]
    candidates = safe(_resolve_stage, customer, watchlist, default=[], label="resolve")

    assessment = safe(_assess, customer, candidates, signals, default=None, label="assess")
    if assessment is None:
        assessment = _stub_assessment(customer, candidates, signals)
    if external_signals:
        # Golden/stub assessments predate the live trigger — attach it so the
        # investigation stage (and the UI) can trace the case back to the event.
        extra_ids = [s.signal_id for s in external_signals
                     if s.signal_id not in assessment.contributing_signals]
        if extra_ids:
            assessment = assessment.model_copy(update={
                "contributing_signals": [*assessment.contributing_signals, *extra_ids]})

    sar = None
    if assessment.tier != "NONE":
        # Gate investigation: only spend it where it can change the answer — the
        # contextual/ambiguous tiers (CRITICAL, EDD) or when the resolver left a
        # candidate AMBIGUOUS. A deterministic HIGH (PAN-exact, confidence 1.0) is
        # already settled and skips investigation. draft_sar still runs regardless;
        # for a skipped case it simply receives empty evidence.
        needs_investigation = (assessment.tier in ("CRITICAL", "EDD")
                               or any(c.decision == "AMBIGUOUS" for c in candidates))
        if needs_investigation:
            # Hand investigate() THIS run's reference data (live signals, resolved
            # candidates, merged watchlist) on top of the fixtures it defaults to,
            # so external triggers are visible to the corroboration probes.
            src = {
                "signals": [*_fx("signals"),
                            *(s.model_dump(mode="json") for s in (external_signals or []))],
                "candidates": [*_fx("candidates"),
                               *(c.model_dump(mode="json") for c in candidates)],
                "watchlist": [w.model_dump(mode="json") for w in watchlist],
            }
            # use_llm=False pins the deterministic adjudicator (no Anthropic call);
            # use_llm=True lets investigate() choose LLM-vs-fallback by key presence.
            # The documented seam is `investigate(assessment)` — tests and future
            # implementations may swap in exactly that — so the optional kwargs are
            # only passed when the installed function actually accepts them.
            import inspect
            accepted = inspect.signature(investigate).parameters
            kwargs = {}
            if "adjudicate" in accepted and not use_llm:
                kwargs["adjudicate"] = deterministic_adjudicator
            if "sources" in accepted:
                kwargs["sources"] = src
            evidence = safe(lambda a: investigate(a, **kwargs),
                            assessment, default=[], label="investigate")
        else:
            evidence = []
        sar = safe(draft_sar, assessment, evidence, customer, default=None, label="draft_sar")

    case = build_case(customer, assessment, sar)

    ts = assessment.assessed_at
    audit = [
        _audit("RESOLVED", "Customer", customer.client_id, ts,
               f"{len(candidates)} candidate(s); "
               f"{sum(c.decision == 'REJECTED' for c in candidates)} suppressed", 1, case.case_id),
        _audit("ASSESSED", "RiskAssessment", assessment.assessment_id, ts,
               f"tier {assessment.prior_tier} -> {assessment.tier}; "
               f"gates {assessment.gates_fired or '[]'}", 2, case.case_id),
        _audit("CASE_OPENED", "Case", case.case_id, ts,
               f"status {case.status}, tier {case.tier}", 3, case.case_id),
    ]

    # Each external trigger becomes a SIGNAL timeline event + an audit row, so the
    # UI's risk timeline and the append-only trail both show WHAT started this run.
    for s in (external_signals or []):
        case.timeline.insert(0, TimelineEvent(
            at=s.occurred_at, kind="SIGNAL",
            summary=f"[{s.source}] {s.headline}"[:200],
            evidence_ids=[], tier_before=assessment.prior_tier,
            tier_after=assessment.prior_tier, dedup_key=s.content_hash or None,
            resolution_confidence=s.source_credibility))
        actor = ("agent:sanctions" if s.signal_type == "WATCHLIST_DELTA"
                 else "agent:signals")
        audit.insert(0, AuditEvent(
            audit_id=f"AUD-{case.case_id}-0-{uuid4().hex[:8]}", at=s.ingested_at,
            actor=actor, action="SIGNAL_INGESTED", object_type="Signal",
            object_id=s.signal_id,
            rationale=f"{s.signal_type} from {s.source}: {s.headline}"[:300]))
    case.timeline.sort(key=lambda t: t.at)

    if persist_result:
        case = _merge_with_prior(case)
        persist(case, assessments=[assessment], audit=audit,
                customer=customer, candidates=candidates)
    return case


def seed_from_fixtures(use_llm: bool = False) -> list[Case]:
    """Rebuild the DB and run every fixture customer through the pipeline. Used by
    the API on startup and by tests so there are persisted Cases to read.

    use_llm defaults to False: seeding ALWAYS uses the deterministic adjudicator, so
    server boot makes zero Anthropic API calls even when a key is set. Live LLM
    adjudication happens only on an interactive POST /api/pipeline/{id} run."""
    init_db()
    return [run_pipeline(Customer(**c), use_llm=use_llm) for c in _fx("customers")]
