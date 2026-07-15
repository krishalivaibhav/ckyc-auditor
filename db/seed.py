"""Seed the SQLite sink (`ckyc.db`) with demo data for the Flutter dashboard.

Why this exists
---------------
`db/schema.sql` *defines* the sink but nothing had ever materialised it — there was
no `ckyc.db` file and no data. The real agent pipeline (core/orchestrator.py) is the
production writer via `db/store.py`; until it runs on this machine, this script stands
in for it so the UI has something real to read over the local API.

It writes the SAME three tables the pipeline writes — `cases`, `sars`,
`audit_events` — using only the standard library (no `contracts.models`, which is not
present in this repo). The JSON blob shape matches exactly what the Flutter models
parse (see lib/models/models.dart). Suppressions are stored as append-only
`audit_events` with action='SUPPRESSED' — the schema's own comment lists SUPPRESSED as
a first-class audit action, and the risk timeline + suppression log both derive from
this table.

Run:  python3 db/seed.py            # rebuilds ckyc.db from scratch
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "schema.sql"
DB = ROOT / "ckyc.db"

CR = 10_000_000.0   # 1 crore in rupees
LAKH = 100_000.0    # 1 lakh in rupees

_NOW = datetime.now(timezone.utc)


def days_ago(n: int) -> str:
    return (_NOW - timedelta(days=n)).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# Cases. Each blob is a superset the API projects into the per-screen payloads:
#   alert    = client_id,name,type,tier,status,exposure_inr,case_id
#   entity360= customer + assessment + candidate
#   timeline = timeline[]
#   case     = case_id,client_id,customer,assessment,evidence,sar,reviewer_actions,decision
#   sar      = sar
# A case with status='suppressed' is excluded from the alert queue but still
# serves an Entity 360 (e.g. Anand Sharma, the PAN-mismatch reject).
# ──────────────────────────────────────────────────────────────────────────────
CASES = [
    {
        "case_id": "case-2001",
        "client_id": "c-2001",
        "opened_at": days_ago(4),
        "status": "in_review",
        "tier": "CRITICAL",
        "customer": {"client_id": "c-2001", "name": "Rajesh Malhotra",
                     "type": "Individual", "pan": "AAAPM1234C", "city": "Delhi"},
        "assessment": {"tier": "CRITICAL", "score": 0.97, "exposure_inr": 2 * LAKH,
                       "gates_fired": ["UAPA_EXACT_PAN", "ADVERSE_MEDIA_CORROBORATION"],
                       "suppressions": []},
        "candidate": {"candidate_id": "mha-uapa-0091", "matched_name": "Rajesh Malhotra",
                      "matched_pan": "AAAPM1234C", "matched_type": "Individual",
                      "list_name": "MHA UAPA", "match_method": "PAN_EXACT",
                      "confidence": 0.98, "rejection_reason": None},
        "evidence": [
            {"ev_id": "EV-001", "column": "confirmed",
             "claim": "PAN exact match to MHA UAPA notification",
             "source_name": "MHA UAPA notification S.O. 4231(E)",
             "source_url": "https://www.mha.gov.in/sites/default/files/uapa-notification.pdf",
             "excerpt": "Individual listed under the Unlawful Activities (Prevention) Act; PAN AAAPM1234C.",
             "confidence": 0.98},
            {"ev_id": "EV-002", "column": "confirmed",
             "claim": "Adverse media naming the individual in a terror-financing probe",
             "source_name": "The Hindu",
             "source_url": "https://www.thehindu.com/news/example-uapa-probe",
             "excerpt": "Investigators named Rajesh Malhotra among those under scrutiny for cross-border transfers.",
             "confidence": 0.71},
            {"ev_id": "EV-003", "column": "correlated",
             "claim": "Same name and city as a separate PEP record - no shared identifier",
             "source_name": "PEP register",
             "source_url": None,
             "excerpt": "A \"Rajesh Malhotra\" of Delhi appears on a PEP list, but with no matching PAN or DOB.",
             "confidence": 0.35},
            {"ev_id": "EV-004", "column": "missing",
             "claim": "Company registry record for the linked entity not retrievable",
             "source_name": "MCA21", "source_url": None,
             "excerpt": "Lookup returned no record; registry may be stale.", "confidence": None},
        ],
        "timeline": [
            {"id": "te-2001-1", "client_id": "c-2001", "date": days_ago(20),
             "event": "Onboarded - routine screening, no hits", "evidence_refs": [],
             "tier_before": "MONITOR", "tier_after": "MONITOR"},
            {"id": "te-2001-2", "client_id": "c-2001", "date": days_ago(4),
             "event": "Exact PAN match to MHA UAPA notification - escalated to CRITICAL",
             "evidence_refs": ["EV-001"], "tier_before": "MONITOR", "tier_after": "CRITICAL"},
            {"id": "te-2001-3", "client_id": "c-2001", "date": days_ago(3),
             "event": "Adverse media corroborates listing", "evidence_refs": ["EV-002"],
             "tier_before": "CRITICAL", "tier_after": "CRITICAL"},
        ],
        "sar": {
            "case_id": "case-2001",
            "body": ("Subject Rajesh Malhotra (PAN AAAPM1234C) is an exact PAN match to an individual "
                     "listed under the Unlawful Activities (Prevention) Act [EV-001]. Adverse media "
                     "independently names the subject in a terror-financing investigation involving "
                     "cross-border transfers [EV-002]. Given a confirmed UAPA listing corroborated by "
                     "media, we recommend filing a Suspicious Activity Report and freezing further "
                     "transactions pending review."),
            "citation_coverage": 0.86,
            "unverified_claims": [
                "Alleged offshore account in Dubai - no corroborating source located.",
                "Reported family link to a second listed individual - could not be verified.",
            ],
            "status": "draft",
        },
        "reviewer_actions": [],
        "decision": None,
    },
    {
        "case_id": "case-2002",
        "client_id": "c-2002",
        "opened_at": days_ago(6),
        "status": "open",
        "tier": "HIGH",
        "customer": {"client_id": "c-2002", "name": "Vertex Commodities Pvt Ltd",
                     "type": "Company", "pan": "AABCV7788K", "city": "Ahmedabad"},
        "assessment": {"tier": "HIGH", "score": 0.74, "exposure_inr": 50 * CR,
                       "gates_fired": ["SEBI_DEBAR_CIN_MATCH", "HIGH_EXPOSURE"],
                       "suppressions": []},
        "candidate": {"candidate_id": "sebi-debar-2210",
                      "matched_name": "Vertex Commodities Private Limited",
                      "matched_pan": "AABCV7788K", "matched_type": "Company",
                      "list_name": "NSE/SEBI debarred", "match_method": "CIN_EXACT",
                      "confidence": 0.91, "rejection_reason": None},
        "evidence": [
            {"ev_id": "EV-050", "column": "confirmed",
             "claim": "CIN exact match to an NSE/SEBI debarment order",
             "source_name": "SEBI order WTM/2023/1187",
             "source_url": "https://www.sebi.gov.in/enforcement/orders/example.pdf",
             "excerpt": "Entity debarred from the securities market for two years.",
             "confidence": 0.91},
            {"ev_id": "EV-051", "column": "correlated",
             "claim": "Directors overlap with a second debarred company",
             "source_name": "MCA21 director index", "source_url": None,
             "excerpt": "Two common DINs across the two entities.", "confidence": 0.48},
            {"ev_id": "EV-052", "column": "missing",
             "claim": "Ultimate beneficial owner declaration not on file",
             "source_name": "Internal KYC", "source_url": None,
             "excerpt": "UBO field blank in the onboarding packet.", "confidence": None},
        ],
        "timeline": [],
        "sar": {
            "case_id": "case-2002",
            "body": ("Vertex Commodities Pvt Ltd (CIN-matched) is subject to an active SEBI debarment "
                     "order [EV-050]. With Rs 50cr of exposure and a directorship overlap with a second "
                     "debarred entity [EV-051], enhanced due diligence and senior sign-off are "
                     "recommended before any further limit is extended."),
            "citation_coverage": 0.79,
            "unverified_claims": [
                "Suspected shell subsidiary in Singapore - registry lookup pending.",
            ],
            "status": "draft",
        },
        "reviewer_actions": [],
        "decision": None,
    },
    {
        "case_id": "case-2003",
        "client_id": "c-2003",
        "opened_at": days_ago(60),
        "status": "open",
        "tier": "EDD",
        "customer": {"client_id": "c-2003", "name": "Sterling Exports Ltd",
                     "type": "Company", "pan": "AACCS9012F", "city": "Surat"},
        "assessment": {"tier": "EDD", "score": 0.44, "exposure_inr": 8 * CR,
                       "gates_fired": ["SEBI_ORDER_REVOKED"], "suppressions": []},
        "candidate": None,
        "evidence": [
            {"ev_id": "EV-101", "column": "confirmed",
             "claim": "Named in a SEBI interim debarment order",
             "source_name": "SEBI interim order",
             "source_url": "https://www.sebi.gov.in/enforcement/orders/interim.pdf",
             "excerpt": "Interim restraint pending investigation.", "confidence": 0.88},
            {"ev_id": "EV-102", "column": "confirmed",
             "claim": "SEBI interim order revoked on appeal",
             "source_name": "SAT order",
             "source_url": "https://sat.gov.in/orders/example-revocation.pdf",
             "excerpt": "Securities Appellate Tribunal set aside the interim restraint.",
             "confidence": 0.9},
        ],
        "timeline": [
            {"id": "te-2003-1", "client_id": "c-2003", "date": days_ago(60),
             "event": "Named in SEBI interim debarment order - escalated to HIGH",
             "evidence_refs": ["EV-101"], "tier_before": "MONITOR", "tier_after": "HIGH"},
            {"id": "te-2003-2", "client_id": "c-2003", "date": days_ago(7),
             "event": "SEBI interim order revoked on appeal - risk DE-ESCALATED to EDD",
             "evidence_refs": ["EV-102"], "tier_before": "HIGH", "tier_after": "EDD"},
        ],
        "sar": None,
        "reviewer_actions": [],
        "decision": None,
    },
    {
        "case_id": "case-3001",
        "client_id": "c-3001",
        "opened_at": days_ago(9),
        "status": "open",
        "tier": "EDD_LITE",
        "customer": {"client_id": "c-3001", "name": "Neha Kapoor",
                     "type": "Individual", "pan": "AKKPK4567L", "city": "Pune"},
        "assessment": {"tier": "EDD_LITE", "score": 0.28, "exposure_inr": 40 * LAKH,
                       "gates_fired": ["ADVERSE_MEDIA_WEAK"], "suppressions": []},
        "candidate": None,
        "evidence": [],
        "timeline": [],
        "sar": None,
        "reviewer_actions": [],
        "decision": None,
    },
    {
        "case_id": "case-3002",
        "client_id": "c-3002",
        "opened_at": days_ago(11),
        "status": "open",
        "tier": "MONITOR",
        "customer": {"client_id": "c-3002", "name": "Coastal Logistics LLP",
                     "type": "Company", "pan": "AAJCL1122M", "city": "Kochi"},
        "assessment": {"tier": "MONITOR", "score": 0.09, "exposure_inr": 12 * LAKH,
                       "gates_fired": [], "suppressions": []},
        "candidate": None,
        "evidence": [],
        "timeline": [],
        "sar": None,
        "reviewer_actions": [],
        "decision": None,
    },
    {
        # Suppressed (PAN mismatch). status='suppressed' keeps it OUT of the alert
        # queue but its Entity 360 still explains WHY it was not raised.
        "case_id": "case-1001",
        "client_id": "c-1001",
        "opened_at": days_ago(15),
        "status": "suppressed",
        "tier": "MONITOR",
        "customer": {"client_id": "c-1001", "name": "Anand Sharma",
                     "type": "Individual", "pan": "BGJPS5517E", "city": "Mumbai"},
        "assessment": {"tier": "MONITOR", "score": 0.12, "exposure_inr": 5 * LAKH,
                       "gates_fired": [], "suppressions": ["PAN_MISMATCH_REJECT"]},
        "candidate": {"candidate_id": "nse-debar-4471", "matched_name": "Anand Sharma",
                      "matched_pan": "ATFPS5670Q", "matched_type": "Individual",
                      "list_name": "NSE/SEBI debarred", "match_method": "NAME_ONLY",
                      "confidence": 0.41,
                      "rejection_reason": ("PAN mismatch: client BGJPS5517E vs debarred entry "
                                           "ATFPS5670Q. Same name, different person - not raised.")},
        "evidence": [],
        "timeline": [],
        "sar": None,
        "reviewer_actions": [],
        "decision": None,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Audit trail. Pipeline steps (per client) + the three SUPPRESSED rows that the
# suppression log (Screen 5) derives from. `after` carries the structured payload
# the /api/suppressions endpoint projects into {customer, matched, method, reason}.
# ──────────────────────────────────────────────────────────────────────────────
def _audit(audit_id, at, actor, action, object_id, rationale,
           object_type="case", before=None, after=None):
    return {"audit_id": audit_id, "at": at, "actor": actor, "action": action,
            "object_type": object_type, "object_id": object_id,
            "before": before, "after": after, "rationale": rationale}


AUDIT = [
    _audit("al-2001-1", days_ago(4), "agent:sanctions-agent", "SCREENED", "c-2001",
           "Screened against MHA UAPA + NSE/SEBI lists", after={"candidates": 1}),
    _audit("al-2001-2", days_ago(4), "agent:entity-resolution", "RESOLVED", "c-2001",
           "PAN exact match confirmed", after={"verdict": "confirmed_match"}),
    _audit("al-2001-3", days_ago(4), "agent:risk-scorer", "ASSESSED", "c-2001",
           "UAPA exact PAN -> CRITICAL", after={"tier": "CRITICAL", "score": 0.97}),
    _audit("al-2001-4", days_ago(4), "agent:orchestrator", "CASE_OPENED", "c-2001",
           "Case opened for human review", after={"case_id": "case-2001"}),
    _audit("al-2001-5", days_ago(3), "agent:investigation-agent", "SAR_DRAFTED", "c-2001",
           "Draft SAR generated with 86% citation coverage", after={"case_id": "case-2001"}),

    _audit("al-2002-1", days_ago(6), "agent:sanctions-agent", "SCREENED", "c-2002",
           "CIN match to SEBI debarment order", after={"candidates": 1}),
    _audit("al-2002-2", days_ago(6), "agent:risk-scorer", "ASSESSED", "c-2002",
           "SEBI debar + Rs 50cr exposure -> HIGH", after={"tier": "HIGH", "score": 0.74}),
    _audit("al-2002-3", days_ago(6), "agent:orchestrator", "CASE_OPENED", "c-2002",
           "Case opened", after={"case_id": "case-2002"}),
    _audit("al-2002-4", days_ago(5), "agent:investigation-agent", "SAR_DRAFTED", "c-2002",
           "Draft SAR generated", after={"case_id": "case-2002"}),

    _audit("al-2003-1", days_ago(60), "agent:risk-scorer", "ASSESSED", "c-2003",
           "SEBI interim order -> HIGH", after={"tier": "HIGH"}),
    _audit("al-2003-2", days_ago(7), "agent:risk-scorer", "ASSESSED", "c-2003",
           "SEBI order revoked on appeal -> DE-ESCALATED to EDD",
           before={"tier": "HIGH"}, after={"tier": "EDD"}),

    # Suppression log (the false positives we refused to raise).
    _audit("sup-1", days_ago(15), "agent:risk-scorer", "SUPPRESSED", "c-1001",
           "PAN mismatch - different person", object_type="suppression",
           after={"customer": "Anand Sharma", "matched": "NSE/SEBI debarred",
                  "method": "PAN_MISMATCH_REJECT",
                  "reason": ("PAN BGJPS5517E != ATFPS5670Q -> different person. "
                             "Names collide but the identifiers do not.")}),
    _audit("sup-2", days_ago(12), "agent:risk-scorer", "SUPPRESSED", "amir-khan",
           "Bare alias with no corroborating identifier", object_type="suppression",
           after={"customer": "Amir Khan", "matched": "MHA UAPA",
                  "method": "ALIAS_BARE_REJECT",
                  "reason": ("Matched only the bare alias \"Amir Khan\" with no DOB, PAN or "
                             "nationality to corroborate - requires a second identifier before "
                             "we will raise it.")}),
    _audit("sup-3", days_ago(10), "agent:risk-scorer", "SUPPRESSED", "ajay-kumar",
           "Two lists share zero identifiers", object_type="suppression",
           after={"customer": "Ajay Kumar", "matched": "PEP + debarred",
                  "method": "CROSS_LIST_NO_LINK",
                  "reason": ("The two source lists share zero identifiers, so we never "
                             "auto-link them into a single higher-risk entity.")}),
]


def seed(db_path: Path = DB) -> None:
    conn = sqlite3.connect(db_path)
    try:
        # Drop children before parents; DROP does not trip the append-only triggers.
        for t in ("audit_events", "sars", "cases"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA.read_text())

        for c in CASES:
            conn.execute(
                "INSERT INTO cases(case_id,client_id,opened_at,status,tier,data)"
                " VALUES (?,?,?,?,?,?)",
                (c["case_id"], c["client_id"], c["opened_at"], c["status"], c["tier"],
                 json.dumps(c)))
            sar = c.get("sar")
            if sar:
                conn.execute(
                    "INSERT INTO sars(sar_id,case_id,drafted_at,subject_name,subject_pan,status,data)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (f"sar-{c['case_id']}", c["case_id"], c["opened_at"],
                     c["customer"]["name"], c["customer"].get("pan"),
                     sar["status"].upper(), json.dumps(sar)))

        for a in AUDIT:
            conn.execute(
                "INSERT INTO audit_events"
                "(audit_id,at,actor,action,object_type,object_id,before,after,rationale)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (a["audit_id"], a["at"], a["actor"], a["action"], a["object_type"],
                 a["object_id"],
                 json.dumps(a["before"]) if a["before"] is not None else None,
                 json.dumps(a["after"]) if a["after"] is not None else None,
                 a["rationale"]))
        conn.commit()
    finally:
        conn.close()
    print(f"Seeded {len(CASES)} cases and {len(AUDIT)} audit events -> {db_path}")


if __name__ == "__main__":
    seed()
