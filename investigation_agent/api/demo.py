"""The judges' demo: a scripted two-phase Vijay Mallya scenario.

TEST MODE. The dashboard toggles live -> test; the read-API forwards here. This
module drives the REAL agent functions — the ER ladder (core/resolver), the
verifier (core/verify), the investigation agent (core/investigate) and the case
assembly (core/orchestrator) — through a deterministic story, narrating every
hand-off to the terminal so the judges can watch the backend flow while the
dashboard updates. Nothing here touches the live sink: the scenario persists to
its own demo DB (ckyc_demo.db), which the read-API serves while in test mode.

    Phase 1  (toggle -> test)      the news agent catches Kingfisher's default;
                                   ambiguity matches the name to our book;
                                   investigation finds no corroborating
                                   identifier yet -> EDD case, SAR drafted.
    Phase 2  (time-skip +15 mo)    two more articles land, then SEBI debars
                                   Vijay Mallya (PAN on the entry). Sanctions
                                   agent fires; ambiguity confirms PAN_EXACT;
                                   investigation corroborates -> CRITICAL,
                                   full SAR with citations.

The 15 months is the real-world gap between the first default reporting and the
regulatory debarment — the demo compresses it to one button.
"""
import hashlib
import os
import sqlite3
import sys
import time as _time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from contracts.models import (AuditEvent, Customer, Evidence, RiskAssessment,
                              SAR, Signal, TimelineEvent, WatchlistEntry)
from core.investigate import deterministic_adjudicator, investigate
from core.orchestrator import build_case
from core.resolver import resolve
from core.verify import verify_hit
from db.store import init_db, persist

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB = Path(os.environ.get("CKYC_DEMO_DB", ROOT / "ckyc_demo.db"))

# module state: which act of the play we are in (0 = not started)
_PHASE = 0
_T0: datetime | None = None

# ── terminal narration ────────────────────────────────────────────────────────
_C = {
    "NEWS AGENT": "\033[96m",       # cyan
    "SANCTIONS AGENT": "\033[93m",  # yellow
    "AMBIGUITY AGENT": "\033[95m",  # magenta
    "INVESTIGATION": "\033[92m",    # green
    "SINK": "\033[94m",             # blue
    "UI": "\033[97m",               # white
}
_R = "\033[0m"
_B = "\033[1m"

# Pacing between narration lines so judges can follow the flow. DEMO_FAST=1
# collapses the sleeps (used by automated verification).
_DELAY = 0.0 if os.environ.get("DEMO_FAST") else 0.55


def _say(tag: str, msg: str, delay: float | None = None):
    color = _C.get(tag, "")
    print(f"  {color}{_B}[{tag:<15}]{_R} {msg}", flush=True)
    _time.sleep(_DELAY if delay is None else delay)


def _banner(text: str):
    print(f"\n{_B}{'═' * 74}\n  {text}\n{'═' * 74}{_R}", flush=True)


# ── the cast ──────────────────────────────────────────────────────────────────
# The scenario replays the REAL Mallya chronology, so the timeline shows the
# dates the story actually happened on — not "now". Anchors:
#   2015-11-13  SBI-led consortium default coverage (phase 1, t0)
#   2016-03-02  subject leaves India; banks move Supreme Court   (t0 + 110d)
#   2016-03-14  ED registers the PMLA case over the IDBI loan    (t0 + 122d)
#   2017-01-25  SEBI debarment order — the "+15 months" time skip (t0 + 439d)
DEMO_T0 = datetime(2015, 11, 13, 9, 14, tzinfo=timezone.utc)


def _customer(t0: datetime) -> Customer:
    return Customer(
        client_id="C9001", client_name="Vijay Mallya", client_type="Individual",
        pan="AEZPM4433K", country="IN", sector="Aviation & Beverages",
        branch="Bengaluru", onboarding_date=date(2011, 4, 18),
        exposure_inr=9_200_000_000,          # ₹920 Cr consortium exposure
        last_kyc_refresh=(t0 - timedelta(days=90)).date())


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _article(sid, at, source, url, headline, excerpt, orgs, typology, severity):
    return Signal(
        signal_id=sid, signal_type="ADVERSE_MEDIA", occurred_at=at,
        ingested_at=at, source=source, source_url=url,
        source_credibility=0.85, headline=headline, raw_excerpt=excerpt,
        content_hash=_hash(headline + url), mentioned_names=["Vijay Mallya"],
        mentioned_orgs=orgs, risk_typology=typology, severity=severity)


def _articles(t0: datetime) -> list[Signal]:
    return [
        _article("SIG-DEMO-001", t0, "RSS:economictimes",
                 "https://economictimes.indiatimes.com/kingfisher-default",
                 "Kingfisher Airlines defaults on ₹9,000-crore loans from "
                 "17-bank consortium led by SBI",
                 "The consortium has declared the airline's promoter-backed "
                 "facilities non-performing; recovery proceedings are being "
                 "considered against promoter Vijay Mallya.",
                 ["SBI", "Kingfisher Airlines"], ["FRAUD"], 0.72),
        # 2016-03-02 — the day the story broke that he had left the country.
        # (distinct times-of-day: real wire hits don't all land at t0's clock)
        _article("SIG-DEMO-002", t0 + timedelta(days=110, hours=7, minutes=48),
                 "RSS:thehindu",
                 "https://www.thehindu.com/mallya-leaves-india",
                 "Vijay Mallya leaves India as banks move Supreme Court "
                 "over ₹9,000-crore dues",
                 "Counsel for the consortium told the Supreme Court the "
                 "businessman had left the country; lenders sought disclosure "
                 "of his assets.",
                 ["Supreme Court", "SBI"], ["FRAUD", "MONEY_LAUNDERING"], 0.81),
        # 2016-03-14 — ED registers the PMLA case over the IDBI loan.
        _article("SIG-DEMO-003", t0 + timedelta(days=122, hours=2, minutes=16),
                 "RSS:reuters",
                 "https://www.reuters.com/ed-mallya-idbi-case",
                 "ED files money-laundering case against Vijay Mallya over "
                 "IDBI Bank loan",
                 "The Enforcement Directorate registered a case under PMLA "
                 "over the ₹900-crore IDBI loan; the CBI is investigating "
                 "sanction of the facility.",
                 ["ED", "CBI", "IDBI Bank"], ["MONEY_LAUNDERING"], 0.9),
    ]


def _sanction_entry(t_sanction: datetime) -> WatchlistEntry:
    return WatchlistEntry(
        watchlist_id="NK-DEMO-VM01", list="NSE_SEBI_DEBARRED",
        entity_type="Individual", name="Vijay Mallya",
        aliases=["Vijay Vittal Mallya"],
        alias_quality={"Vijay Vittal Mallya": "full_name"},
        pan="AEZPM4433K", status="active",
        order_id="SEBI/WTM/GM/EFD/2017/031",
        order_date=t_sanction.date(),
        source_url=["https://www.sebi.gov.in/enforcement/orders/mallya-debarment.pdf"],
        first_seen=t_sanction, last_change=t_sanction)


def _sanction_signal(t_sanction: datetime) -> Signal:
    return Signal(
        signal_id="SIG-DEMO-004", signal_type="WATCHLIST_DELTA",
        occurred_at=t_sanction, ingested_at=t_sanction, source="NSE_CIRCULAR",
        source_url="https://www.sebi.gov.in/enforcement/orders/mallya-debarment.pdf",
        source_credibility=1.0,
        headline="SEBI bars Vijay Mallya from securities market; declared "
                 "wilful defaulter by consortium",
        raw_excerpt="Whole-time member order restrains Vijay Mallya from "
                    "accessing the securities market for the diversion of "
                    "funds from a listed entity.",
        content_hash=_hash("SEBI-DEMO-VM01"),
        mentioned_names=["Vijay Mallya"], mentioned_orgs=["SEBI", "NSE"],
        risk_typology=["REGULATORY_ACTION"], severity=0.97)


def _audit_row(actor, action, obj_type, obj_id, at, rationale) -> AuditEvent:
    return AuditEvent(
        audit_id=f"AUD-DEMO-{uuid4().hex[:10]}", at=at, actor=actor,
        action=action, object_type=obj_type, object_id=obj_id,
        rationale=rationale[:300])


def _signal_event(s: Signal, tier: str) -> TimelineEvent:
    return TimelineEvent(
        at=s.occurred_at, kind="SIGNAL",
        summary=f"[{s.source}] {s.headline}"[:200],
        evidence_ids=[], tier_before=tier, tier_after=tier,
        dedup_key=s.content_hash, resolution_confidence=s.source_credibility)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DEMO_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── phase 1: the first news breaks ───────────────────────────────────────────
def start() -> dict:
    global _PHASE, _T0
    _T0 = DEMO_T0
    t0 = _T0
    customer = _customer(t0)
    a1 = _articles(t0)[0]

    _banner("TEST MODE — scenario start: adverse media hits the wire")
    _say("NEWS AGENT", "scanning sources (RSS/GDELT)…")
    _say("NEWS AGENT", f'HIT  "{a1.headline}"  ({a1.source})')
    _say("NEWS AGENT", 'entity resolution: article is about "Vijay Mallya" '
                       "(confidence 0.85, name verbatim in text)")
    _say("NEWS AGENT", "triage: ADVERSE — typology FRAUD, severity 0.72")
    _say("NEWS AGENT", "→ POST /signals/ingest  (payload: Signal SIG-DEMO-001)")

    _say("AMBIGUITY AGENT", 'resolving "Vijay Mallya" against the customer book…')
    _say("AMBIGUITY AGENT", f"NAME MATCH: customer {customer.client_id} "
                            f"(PAN {customer.pan}, {customer.branch}, "
                            f"exposure ₹{customer.exposure_inr / 1e7:,.0f} Cr)")
    _say("AMBIGUITY AGENT", "no watchlist entry to adjudicate against yet — "
                            "adverse media only; passing to investigation")

    assessment = RiskAssessment(
        assessment_id="ASM-C9001-1", client_id="C9001", assessed_at=t0,
        prior_tier="NONE", tier="EDD", score=0.58,
        gates_fired=["ADVERSE_MEDIA_HIGH_SEVERITY"],
        suppressions=[], contributing_signals=[a1.signal_id],
        contributing_candidates=[],
        evidence=[Evidence(
            evidence_id="EV-DEMO-001", kind="NEWS_ARTICLE", status="CORRELATED",
            claim="National media reports the default of Kingfisher Airlines' "
                  "consortium facilities promoted by the subject.",
            source_name=a1.source, source_url=a1.source_url,
            excerpt=a1.raw_excerpt[:280], retrieved_at=t0, confidence=0.72)],
        explanation="High-severity adverse media reports the subject's promoted "
                    "airline defaulting on a 17-bank consortium exposure "
                    "[EV-DEMO-001]. No watchlist entry corroborates yet — "
                    "enhanced due diligence opened while monitoring for "
                    "regulatory action.")

    _say("INVESTIGATION", "planning corroboration probes for the EDD case…")
    inv = investigate(assessment, adjudicate=deterministic_adjudicator,
                      sources={"signals": [a1.model_dump(mode='json')],
                               "candidates": [], "watchlist": []})
    for ev in inv:
        _say("INVESTIGATION", f"{ev.status:<10} {ev.claim}", delay=0.3)
    evidence = [*assessment.evidence, *inv]
    assessment = assessment.model_copy(update={"evidence": evidence})

    sar = SAR(
        sar_id="SAR-C9001-1", case_id="CASE-C9001", drafted_at=t0,
        subject_name=customer.client_name, subject_pan=customer.pan,
        sections={
            "subject_identification":
                f"{customer.client_name} (PAN {customer.pan}), an Individual "
                f"customer of the {customer.branch} branch, onboarded "
                f"{customer.onboarding_date}. Current exposure INR 920 crore.",
            "basis_for_suspicion":
                "National media reports the default of the subject's promoted "
                "airline on a 17-bank consortium facility [EV-DEMO-001]. No "
                "regulatory or watchlist action corroborates the report yet "
                "[EV-INV-001]; the case is opened at EDD for monitoring.",
            "risk_assessment":
                "Tier EDD. Gate ADVERSE_MEDIA_HIGH_SEVERITY fired on a single "
                "high-credibility source. Soft score 0.58.",
            "recommended_action":
                "Enhanced due diligence. Monitor for regulatory action; "
                "re-assess on any watchlist delta. Human sign-off required "
                "before filing.",
        },
        evidence=evidence, unverified_claims=[], citation_coverage=0.75,
        status="DRAFT")

    _say("INVESTIGATION", "drafting SAR… (citation coverage 75%)")
    case = build_case(customer, assessment, sar)
    case.timeline.insert(0, _signal_event(a1, "NONE"))
    case.timeline.sort(key=lambda t: t.at)

    audit = [
        _audit_row("agent:signals", "SIGNAL_INGESTED", "Signal", a1.signal_id,
                   t0, f"ADVERSE_MEDIA from {a1.source}: {a1.headline}"),
        _audit_row("agent:er", "RESOLVED", "Customer", "C9001", t0,
                   "entity_name matched 1 customer in the book; no watchlist "
                   "candidates at this time"),
        _audit_row("agent:orchestrator", "ASSESSED", "RiskAssessment",
                   assessment.assessment_id, t0,
                   "tier NONE -> EDD; gates ['ADVERSE_MEDIA_HIGH_SEVERITY']"),
        _audit_row("agent:orchestrator", "CASE_OPENED", "Case", case.case_id,
                   t0, f"status {case.status}, tier {case.tier}"),
    ]

    conn = _connect()
    try:
        init_db(conn)
        persist(case, assessments=[assessment], audit=audit, conn=conn,
                customer=customer, candidates=[])
    finally:
        conn.close()

    _say("SINK", f"persisted {case.case_id} (tier {case.tier}, "
                 f"status {case.status}, SAR drafted) → ckyc_demo.db")
    _say("UI", "dashboard refresh → alert queue now shows 1 entity: "
               "Vijay Mallya (EDD)")
    _banner("Phase 1 complete — waiting for the time skip (+15 months)")

    _PHASE = 1
    return {"phase": 1, "case_id": case.case_id, "tier": case.tier}


# ── phase 2: fifteen months later ────────────────────────────────────────────
def timeskip() -> dict:
    global _PHASE, _T0
    if _PHASE < 1 or _T0 is None:
        raise RuntimeError("demo not started — toggle test mode first")
    t0 = _T0
    # 2017-01-25 — the SEBI debarment order (the "+15 months" the button skips).
    t_sanction = t0 + timedelta(days=439, hours=5, minutes=1)
    customer = _customer(t0)
    arts = _articles(t0)
    a1, a2, a3 = arts
    entry = _sanction_entry(t_sanction)
    s4 = _sanction_signal(t_sanction)

    _banner("TIME SKIP +15 MONTHS — the story catches up")
    _say("NEWS AGENT", f'HIT  "{a2.headline}"  ({a2.source})')
    _say("NEWS AGENT", "→ POST /signals/ingest  (SIG-DEMO-002)")
    _say("NEWS AGENT", f'HIT  "{a3.headline}"  ({a3.source})')
    _say("NEWS AGENT", "→ POST /signals/ingest  (SIG-DEMO-003)")

    _say("SANCTIONS AGENT", "watchlist delta detected on NSE/SEBI debarred list…")
    _say("SANCTIONS AGENT", f'ADDITION  "{entry.name}"  '
                            f"(order {entry.order_id}, PAN {entry.pan})")
    _say("SANCTIONS AGENT", "→ POST /api/ingest  (WATCHLIST_DELTA SIG-DEMO-004)")

    # ---- the REAL ER ladder adjudicates the sanction hit
    verdict = verify_hit(customer, [entry])
    candidates = resolve(customer, [entry])
    top = candidates[0]
    _say("AMBIGUITY AGENT", f'verifying hit against customer {customer.client_id}…')
    _say("AMBIGUITY AGENT", f"VERDICT: {verdict['verdict']} — "
                            f"{top.match_method} (confidence {top.confidence:.2f}); "
                            f"customer PAN == watchlist PAN {entry.pan}")

    assessment = RiskAssessment(
        assessment_id="ASM-C9001-2", client_id="C9001",
        assessed_at=t_sanction, prior_tier="EDD", tier="CRITICAL", score=0.94,
        gates_fired=["DEBARRED_PAN_EXACT_ACTIVE", "WILFUL_DEFAULTER_ESCALATION"],
        suppressions=[],
        contributing_signals=[a1.signal_id, a2.signal_id, a3.signal_id,
                              s4.signal_id],
        contributing_candidates=[top.candidate_id],
        evidence=[], explanation="")

    _say("INVESTIGATION", "re-opening the case with the confirmed identifier…")
    inv = investigate(
        assessment, adjudicate=deterministic_adjudicator,
        sources={"signals": [s.model_dump(mode="json") for s in [*arts, s4]],
                 "candidates": [c.model_dump(mode="json") for c in candidates],
                 "watchlist": [entry.model_dump(mode="json")]})
    for ev in inv:
        _say("INVESTIGATION", f"{ev.status:<10} {ev.claim}", delay=0.3)

    explanation = (
        "CRITICAL. The customer's PAN exactly matches an active SEBI debarment "
        "order [EV-INV-002]; adverse media over fifteen months documents the "
        "default, departure from India, and an ED money-laundering case, each "
        "naming the designating authorities [EV-INV-001]. Identity is settled "
        "at identifier level — escalated for human review.")
    assessment = assessment.model_copy(update={
        "evidence": inv, "explanation": explanation})

    chronology = (
        f"{a1.occurred_at.date()}: consortium default reported [EV-DEMO-001]. "
        f"{a2.occurred_at.date()}: subject leaves India; banks move Supreme "
        f"Court [EV-INV-001]. "
        f"{a3.occurred_at.date()}: ED registers PMLA case over the IDBI loan "
        f"[EV-INV-001]. "
        f"{t_sanction.date()}: SEBI debars the subject from the securities "
        f"market (order {entry.order_id}) [EV-INV-002]; risk tier escalated "
        f"EDD -> CRITICAL.")
    sar = SAR(
        sar_id="SAR-C9001-2", case_id="CASE-C9001", drafted_at=t_sanction,
        subject_name=customer.client_name, subject_pan=customer.pan,
        sections={
            "subject_identification":
                f"{customer.client_name} (PAN {customer.pan}), an Individual "
                f"customer of the {customer.branch} branch, onboarded "
                f"{customer.onboarding_date}. Current exposure INR 920 crore "
                f"across consortium facilities.",
            "basis_for_suspicion":
                "The subject's PAN exactly matches an active SEBI debarment "
                "order [EV-INV-002]. Fifteen months of adverse media document "
                "the consortium default, the subject's departure from India "
                "and an ED money-laundering case under PMLA, each naming the "
                "designating authorities [EV-INV-001]. The match rests on an "
                "exact identifier, not name similarity.",
            "chronology_of_events": chronology,
            "evidence_summary":
                "CONFIRMED: PAN-level match to the active SEBI debarment "
                "[EV-INV-002]. CORRELATED: designating-authority mentions "
                "across three independent outlets [EV-INV-001]. MISSING: no "
                "co-accused order linkage was found [EV-INV-003] and the "
                "overseas asset trail could not be independently verified — "
                "both are recorded, not inferred.",
            "risk_assessment":
                "Tier CRITICAL. Gates DEBARRED_PAN_EXACT_ACTIVE and "
                "WILFUL_DEFAULTER_ESCALATION fired on a deterministic "
                "identifier match (ER confidence 1.00) [EV-INV-002]. "
                "Soft score 0.94.",
            "recommended_action":
                "Escalate for immediate compliance review. Freeze securities-"
                "related activity per the SEBI order; report exposure to the "
                "consortium lead. Human sign-off required before filing.",
        },
        evidence=inv,
        unverified_claims=[
            "The subject's overseas asset trail — EXCLUDED: no registry "
            "record was retrievable; the claim is omitted rather than "
            "asserted."],
        citation_coverage=0.92, status="DRAFT")
    _say("INVESTIGATION", "drafting SAR v2… (citation coverage 92%, "
                          "1 claim excluded as unverifiable)")

    case = build_case(customer, assessment, sar)
    # Rebuild the FULL accumulated timeline — phase 1's events plus everything
    # the fifteen months brought. Deterministic story, deterministic history.
    case.timeline = sorted([
        _signal_event(a1, "NONE"),
        TimelineEvent(at=t0, kind="REASSESSMENT",
                      summary="High-severity adverse media on the subject's "
                              "consortium default; EDD opened while awaiting "
                              "corroboration [EV-DEMO-001].",
                      evidence_ids=["EV-DEMO-001"],
                      tier_before="NONE", tier_after="EDD"),
        TimelineEvent(at=t0, kind="SAR",
                      summary="SAR drafted. Citation coverage 75%.",
                      evidence_ids=["EV-DEMO-001"],
                      tier_before="EDD", tier_after="EDD"),
        _signal_event(a2, "EDD"),
        _signal_event(a3, "EDD"),
        _signal_event(s4, "EDD"),
        TimelineEvent(at=t_sanction, kind="REASSESSMENT",
                      summary=explanation[:200],
                      evidence_ids=[e.evidence_id for e in inv],
                      tier_before="EDD", tier_after="CRITICAL"),
        TimelineEvent(at=t_sanction, kind="SAR",
                      summary="SAR v2 drafted. Citation coverage 92%.",
                      evidence_ids=[e.evidence_id for e in inv],
                      tier_before="CRITICAL", tier_after="CRITICAL"),
    ], key=lambda t: t.at)
    case = case.model_copy(update={"opened_at": t0})

    audit = [
        _audit_row("agent:signals", "SIGNAL_INGESTED", "Signal", a2.signal_id,
                   a2.occurred_at, f"ADVERSE_MEDIA from {a2.source}: {a2.headline}"),
        _audit_row("agent:signals", "SIGNAL_INGESTED", "Signal", a3.signal_id,
                   a3.occurred_at, f"ADVERSE_MEDIA from {a3.source}: {a3.headline}"),
        _audit_row("agent:sanctions", "SIGNAL_INGESTED", "Signal", s4.signal_id,
                   t_sanction, f"WATCHLIST_DELTA from {s4.source}: {s4.headline}"),
        _audit_row("agent:er", "RESOLVED", "Customer", "C9001", t_sanction,
                   f"verdict {verdict['verdict']} via {top.match_method} "
                   f"(confidence {top.confidence:.2f})"),
        _audit_row("agent:orchestrator", "ASSESSED", "RiskAssessment",
                   assessment.assessment_id, t_sanction,
                   "tier EDD -> CRITICAL; gates "
                   "['DEBARRED_PAN_EXACT_ACTIVE', 'WILFUL_DEFAULTER_ESCALATION']"),
        _audit_row("agent:orchestrator", "ESCALATED", "Case", case.case_id,
                   t_sanction, "CRITICAL is always-human: routed to reviewer"),
    ]

    conn = _connect()
    try:
        persist(case, assessments=[assessment], audit=audit, conn=conn,
                customer=customer, candidates=candidates)
    finally:
        conn.close()

    _say("SINK", f"persisted {case.case_id} (tier {case.tier}, "
                 f"status {case.status}, SAR v2) → ckyc_demo.db")
    _say("UI", "dashboard refresh → timeline now carries 3 articles + the "
               "SEBI sanction; SAR ready for download")
    _banner("Phase 2 complete — the reviewer takes it from here")

    _PHASE = 2
    return {"phase": 2, "case_id": case.case_id, "tier": case.tier}


def status() -> dict:
    return {"phase": _PHASE, "db": str(DEMO_DB), "db_exists": DEMO_DB.exists()}


if __name__ == "__main__":   # manual smoke run:  .venv/bin/python -m api.demo
    start()
    if "--skip" in sys.argv or True:
        timeskip()
