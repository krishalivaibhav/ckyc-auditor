"""
Generate fixtures/ — one golden JSON file per contract object.

These are the LIFELINE of the build. Samaksh builds the entire dashboard from them
with zero backend; Sneha drafts every SAR from them with zero ER. If they are thin
or unrealistic, two people build the wrong thing.

Seeded from the REAL watchlists so the names, PANs, and NSE circular URLs are
genuine. Run from repo root:  python scripts/make_fixtures.py
"""
import json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
FIX = ROOT / "fixtures"
FIX.mkdir(exist_ok=True)

NOW = datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)
iso = lambda d: d.isoformat()


def ndjson(p):
    with open(DATA / p) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


# ============================================================ real watchlist pulls
deb, pep, rca, uapa = [], [], [], []
for d in ndjson("targets_nested_stock_.json"):
    if d.get("schema") != "LegalEntity":
        continue
    p = d.get("properties", {})
    nm = (p.get("name") or [None])[0]
    pans = [x.strip().upper() for x in p.get("taxNumber", []) if len(x.strip()) == 10]
    sancs = p.get("sanctions", []) or []
    if not nm or not sancs:
        continue
    s0 = sancs[0].get("properties", {})
    urls = [u for u in s0.get("sourceUrl", []) if u.endswith(".pdf")] or s0.get("sourceUrl", [])
    dur = " ".join(s0.get("duration", []))
    deb.append({
        "watchlist_id": d["id"], "name": nm, "pan": pans[0] if pans else None,
        "status": "revoked" if re.search(r"revok", dur, re.I) else "active",
        "order_date": (s0.get("date") or [None])[0],
        "order_text": (s0.get("description") or [""])[0],
        "source_url": urls[:2],
    })

for d in ndjson("targets_nested_sabha_.json"):
    if d.get("schema") != "Person":
        continue
    p = d.get("properties", {})
    nm = (p.get("name") or [None])[0]
    if not nm:
        continue
    r = {"watchlist_id": d["id"], "name": nm,
         "dob": (p.get("birthDate") or [None])[0],
         "party": (p.get("political") or [None])[0]}
    t = p.get("topics", [])
    (pep if "role.pep" in t else rca if "role.rca" in t else []).append(r) if t else None

for d in ndjson("targets_nested_mha_.json"):
    if d.get("schema") != "Person":
        continue
    p = d.get("properties", {})
    nm = (p.get("name") or [None])[0]
    al = [a.strip().strip("\u201d)") for a in p.get("alias", []) if a.strip()]
    if nm:
        uapa.append({"watchlist_id": d["id"], "name": nm, "aliases": al,
                     "source_url": (p.get("sourceUrl") or [""])[:1]})

# pick specific, story-carrying entries
saeed = next(u for u in uapa if "Saeed" in u["name"] and len(u["aliases"]) > 5)
deb_active = next(d for d in deb if d["status"] == "active" and d["pan"] and d["pan"][3] == "P"
                  and d["source_url"])
deb_revoked = next(d for d in deb if d["status"] == "revoked" and d["pan"] and d["source_url"])
deb_corp = next(d for d in deb if d["pan"] and d["pan"][3] == "C" and d["source_url"])
pep0 = next(p for p in pep if p["party"] and p["dob"])
rca0 = rca[3]


def alias_q(a):
    if re.fullmatch(r"\(?[A-Z][A-Z\-()]{1,7}\)?", a):
        return "org_acronym"
    if len(a.split()) == 1:
        return "bare_token"
    if a.lower() in {"amir khan", "gulshan kumar", "abdul manan", "hafiz saeed"}:
        return "bare_token"
    return "full_name"


# ============================================================ 1. watchlist.json
watchlist = [
    {"watchlist_id": deb_active["watchlist_id"], "list": "NSE_SEBI_DEBARRED",
     "entity_type": "Individual", "name": deb_active["name"], "aliases": [], "alias_quality": {},
     "pan": deb_active["pan"], "dob": None, "party": None, "status": "active",
     "order_id": "ORD-a91f", "order_date": deb_active["order_date"],
     "source_url": deb_active["source_url"], "first_seen": iso(NOW - timedelta(days=700)),
     "last_change": iso(NOW - timedelta(days=40))},
    {"watchlist_id": deb_revoked["watchlist_id"], "list": "NSE_SEBI_DEBARRED",
     "entity_type": "Individual", "name": deb_revoked["name"], "aliases": [], "alias_quality": {},
     "pan": deb_revoked["pan"], "dob": None, "party": None, "status": "revoked",
     "order_id": "ORD-c72b", "order_date": deb_revoked["order_date"],
     "source_url": deb_revoked["source_url"], "first_seen": iso(NOW - timedelta(days=900)),
     "last_change": iso(NOW - timedelta(days=9))},
    {"watchlist_id": deb_corp["watchlist_id"], "list": "NSE_SEBI_DEBARRED",
     "entity_type": "Corporate", "name": deb_corp["name"], "aliases": [], "alias_quality": {},
     "pan": deb_corp["pan"], "dob": None, "party": None, "status": "active",
     "order_id": "ORD-a91f", "order_date": deb_corp["order_date"],
     "source_url": deb_corp["source_url"], "first_seen": iso(NOW - timedelta(days=700)),
     "last_change": iso(NOW - timedelta(days=40))},
    {"watchlist_id": pep0["watchlist_id"], "list": "SABHA_PEP_CURRENT",
     "entity_type": "Individual", "name": pep0["name"], "aliases": [], "alias_quality": {},
     "pan": None, "dob": pep0["dob"], "party": pep0["party"], "status": "current",
     "order_id": None, "order_date": None,
     "source_url": ["https://sansad.in/ls/members"],
     "first_seen": iso(NOW - timedelta(days=600)), "last_change": iso(NOW - timedelta(days=10))},
    {"watchlist_id": rca0["watchlist_id"], "list": "SABHA_RCA",
     "entity_type": "Individual", "name": rca0["name"], "aliases": [], "alias_quality": {},
     "pan": None, "dob": rca0.get("dob"), "party": None, "status": "current",
     "order_id": None, "order_date": None, "source_url": ["https://sansad.in/ls/members"],
     "first_seen": iso(NOW - timedelta(days=600)), "last_change": iso(NOW - timedelta(days=10))},
    {"watchlist_id": saeed["watchlist_id"], "list": "MHA_UAPA",
     "entity_type": "Individual", "name": saeed["name"], "aliases": saeed["aliases"],
     "alias_quality": {a: alias_q(a) for a in saeed["aliases"]},
     "pan": None, "dob": None, "party": None, "status": "active",
     "order_id": None, "order_date": None, "source_url": saeed["source_url"],
     "first_seen": iso(NOW - timedelta(days=800)), "last_change": iso(NOW - timedelta(days=60))},
]
# + 24 more real debarred entries so blocking/indexing has something to chew on
for d in [x for x in deb if x["pan"]][:24]:
    watchlist.append({
        "watchlist_id": d["watchlist_id"], "list": "NSE_SEBI_DEBARRED",
        "entity_type": {"P": "Individual", "C": "Corporate"}.get(d["pan"][3], "Unknown"),
        "name": d["name"], "aliases": [], "alias_quality": {}, "pan": d["pan"],
        "dob": None, "party": None, "status": d["status"], "order_id": "ORD-misc",
        "order_date": d["order_date"], "source_url": d["source_url"],
        "first_seen": iso(NOW - timedelta(days=500)), "last_change": iso(NOW - timedelta(days=80))})

# ============================================================ 2. customers.json
customers = [
    # A_TRUE_SANCTION — real name + real PAN. must fire HIGH.
    {"client_id": "C1001", "client_name": deb_active["name"], "client_type": "Individual",
     "pan": deb_active["pan"], "country": "IN", "sector": "Commodities", "branch": "Mumbai",
     "onboarding_date": "2021-03-14", "exposure_inr": 48_200_000, "last_kyc_refresh": "2024-02-01"},
    # B_FP_PAN_MISMATCH — same name, DIFFERENT PAN. must SUPPRESS.
    {"client_id": "C1002", "client_name": deb_active["name"], "client_type": "Individual",
     "pan": "AFOPG8341M", "country": "IN", "sector": "IT Services", "branch": "Pune",
     "onboarding_date": "2022-08-02", "exposure_inr": 1_950_000, "last_kyc_refresh": "2025-01-19"},
    # F_FP_UAPA_ALIAS — bare alias. must SUPPRESS.
    {"client_id": "C1003", "client_name": "Amir Khan", "client_type": "Individual",
     "pan": "BQMPK4471J", "country": "IN", "sector": "Import/Export", "branch": "Delhi",
     "onboarding_date": "2020-11-30", "exposure_inr": 7_400_000, "last_kyc_refresh": "2024-09-05"},
    # C_FP_PEP_COLLISION — on BOTH lists, zero shared identifiers. must NOT auto-link.
    {"client_id": "C1004", "client_name": pep0["name"], "client_type": "Individual",
     "pan": "CJKPS1180Q", "country": "IN", "sector": "Real Estate", "branch": "Lucknow",
     "onboarding_date": "2019-06-11", "exposure_inr": 132_000_000, "last_kyc_refresh": "2023-11-22"},
    # D_TRUE_PEP — real sitting MP. EDD, not adverse.
    {"client_id": "C1005", "client_name": pep0["name"], "client_type": "Individual",
     "pan": None, "country": "IN", "sector": "NBFC", "branch": "Delhi",
     "onboarding_date": "2023-01-09", "exposure_inr": 21_500_000, "last_kyc_refresh": "2025-06-30"},
    # E_TRUE_RCA — spouse of an MP. EDD_LITE.
    {"client_id": "C1006", "client_name": rca0["name"], "client_type": "Individual",
     "pan": "AKTPR9023F", "country": "IN", "sector": "Pharma", "branch": "Bengaluru",
     "onboarding_date": "2022-04-18", "exposure_inr": 6_100_000, "last_kyc_refresh": "2025-03-12"},
    # G_TRUE_UAPA — transliteration variant. must fire CRITICAL.
    {"client_id": "C1007", "client_name": saeed["aliases"][0], "client_type": "Individual",
     "pan": None, "country": "IN", "sector": "NGO/Charity", "branch": "Delhi",
     "onboarding_date": "2020-02-27", "exposure_inr": 890_000, "last_kyc_refresh": "2023-08-14"},
    # A corporate hit (noisy record: "SURNAME, First" style corruption)
    {"client_id": "C1008", "client_name": deb_corp["name"].upper(), "client_type": "Corporate",
     "pan": deb_corp["pan"], "country": "IN", "sector": "Infrastructure", "branch": "Ahmedabad",
     "onboarding_date": "2021-09-03", "exposure_inr": 264_000_000, "last_kyc_refresh": "2024-05-20"},
    # de-escalation case: revoked order
    {"client_id": "C1009", "client_name": deb_revoked["name"], "client_type": "Individual",
     "pan": deb_revoked["pan"], "country": "IN", "sector": "Financial Services", "branch": "Kolkata",
     "onboarding_date": "2019-12-01", "exposure_inr": 15_300_000, "last_kyc_refresh": "2024-12-08"},
    # H_CLEAN
    {"client_id": "C1010", "client_name": "Tanvi Chatterjee", "client_type": "Individual",
     "pan": "GBYPC8945Y", "country": "IN", "sector": "IT Services", "branch": "Kolkata",
     "onboarding_date": "2023-07-21", "exposure_inr": 3_200_000, "last_kyc_refresh": "2025-07-01"},
]

# ============================================================ 3. signals.json
signals = [
    {"signal_id": "SIG-0001", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=2)), "ingested_at": iso(NOW - timedelta(days=2, hours=-1)),
     "source": "RSS:economictimes", "source_url": "https://economictimes.indiatimes.com/markets/example-sebi-order",
     "source_credibility": 0.9,
     "headline": f"SEBI bars {deb_active['name']} from securities market in front-running probe",
     "raw_excerpt": f"The regulator has restrained {deb_active['name']} from accessing the securities "
                    f"market, citing evidence of front-running in the matter under investigation.",
     "content_hash": "a1f9c2...", "story_cluster_id": "CL-0001",
     "mentioned_names": [deb_active["name"]], "mentioned_orgs": ["SEBI"],
     "risk_typology": ["MARKET_MANIPULATION", "REGULATORY_ACTION"],
     "severity": 0.82, "is_rehash": False},
    {"signal_id": "SIG-0002", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=2, hours=3)), "ingested_at": iso(NOW - timedelta(days=2)),
     "source": "RSS:businessstandard", "source_url": "https://www.business-standard.com/markets/example",
     "source_credibility": 0.85,
     "headline": f"Regulator restrains {deb_active['name']} in front-running case",
     "raw_excerpt": "Same event, different outlet. Must collapse into story_cluster_id CL-0001 "
                    "and produce ONE alert, not two.",
     "content_hash": "b7e0d1...", "story_cluster_id": "CL-0001",
     "mentioned_names": [deb_active["name"]], "mentioned_orgs": ["SEBI"],
     "risk_typology": ["MARKET_MANIPULATION"], "severity": 0.80, "is_rehash": False},
    {"signal_id": "SIG-0003", "signal_type": "WATCHLIST_DELTA",
     "occurred_at": iso(NOW - timedelta(days=9)), "ingested_at": iso(NOW - timedelta(days=9)),
     "source": "NSE_CIRCULAR", "source_url": deb_revoked["source_url"][0] if deb_revoked["source_url"] else "",
     "source_credibility": 1.0,
     "headline": f"NSE revokes debarment: {deb_revoked['name']}",
     "raw_excerpt": "Debarment revoked per NSE circular. Risk profile must DE-ESCALATE. "
                    "Zero press coverage — proves the system does not depend on news.",
     "content_hash": "c3aa77...", "story_cluster_id": None,
     "mentioned_names": [deb_revoked["name"]], "mentioned_orgs": ["NSE"],
     "risk_typology": ["REGULATORY_ACTION"], "severity": 0.0, "is_rehash": False},
    {"signal_id": "SIG-0004", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=1)), "ingested_at": iso(NOW - timedelta(hours=20)),
     "source": "GDELT", "source_url": "https://example-news.in/appointment",
     "source_credibility": 0.6,
     "headline": f"{pep0['name']} appointed to parliamentary standing committee",
     "raw_excerpt": "NOT adverse media. The triage agent must return risk_typology=[NONE]. "
                    "Most naive systems flag this.",
     "content_hash": "d90f2e...", "story_cluster_id": "CL-0004",
     "mentioned_names": [pep0["name"]], "mentioned_orgs": [],
     "risk_typology": ["NONE"], "severity": 0.0, "is_rehash": False},
    {"signal_id": "SIG-0005", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=1400)), "ingested_at": iso(NOW - timedelta(days=3)),
     "source": "GDELT", "source_url": "https://example-news.in/retrospective",
     "source_credibility": 0.4,
     "headline": f"Five years on: the {deb_active['name']} case revisited",
     "raw_excerpt": "A re-report of an OLD event. is_rehash=true -> recency decay must "
                    "down-weight it. Not new risk.",
     "content_hash": "e11b44...", "story_cluster_id": "CL-0005",
     "mentioned_names": [deb_active["name"]], "mentioned_orgs": [],
     "risk_typology": ["MARKET_MANIPULATION"], "severity": 0.30, "is_rehash": True},
    {"signal_id": "SIG-0006", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=4)), "ingested_at": iso(NOW - timedelta(days=4)),
     "source": "GDELT", "source_url": "https://example-news.in/terror-financing",
     "source_credibility": 0.95,
     "headline": f"NIA names {saeed['name']} in cross-border financing chargesheet",
     "raw_excerpt": "Article spells the name as one of eight transliterations. Phonetic "
                    "matching required. UAPA gate -> CRITICAL -> always human review.",
     "content_hash": "f22c88...", "story_cluster_id": "CL-0006",
     "mentioned_names": [saeed["aliases"][0]], "mentioned_orgs": ["NIA"],
     "risk_typology": ["TERRORISM"], "severity": 0.98, "is_rehash": False},
    {"signal_id": "SIG-0007", "signal_type": "EXEC_TURNOVER",
     "occurred_at": iso(NOW - timedelta(days=6)), "ingested_at": iso(NOW - timedelta(days=6)),
     "source": "RSS:moneycontrol", "source_url": "https://www.moneycontrol.com/news/example",
     "source_credibility": 0.8,
     "headline": f"{deb_corp['name']} announces sudden CFO exit",
     "raw_excerpt": "Rapid executive turnover — the PS names this explicitly as a trigger.",
     "content_hash": "091aa3...", "story_cluster_id": "CL-0007",
     "mentioned_names": [], "mentioned_orgs": [deb_corp["name"]],
     "risk_typology": ["REGULATORY_ACTION"], "severity": 0.45, "is_rehash": False},
    {"signal_id": "SIG-0008", "signal_type": "ADVERSE_MEDIA",
     "occurred_at": iso(NOW - timedelta(days=5)), "ingested_at": iso(NOW - timedelta(days=5)),
     "source": "GDELT", "source_url": "https://example-news.in/unrelated-amir-khan",
     "source_credibility": 0.5,
     "headline": "Amir Khan wins district cricket tournament",
     "raw_excerpt": "Matches the bare UAPA alias 'Amir Khan'. Must be SUPPRESSED. "
                    "This is the false positive that drowns compliance teams.",
     "content_hash": "aa3390...", "story_cluster_id": "CL-0008",
     "mentioned_names": ["Amir Khan"], "mentioned_orgs": [],
     "risk_typology": ["NONE"], "severity": 0.0, "is_rehash": False},
]

# ============================================================ 4. candidates.json
candidates = [
    {"candidate_id": "CAND-001", "client_id": "C1001", "watchlist_id": deb_active["watchlist_id"],
     "signal_id": "SIG-0001", "match_method": "PAN_EXACT", "confidence": 1.0,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"pan_match": True, "name_similarity": 1.0, "list_status": "active"}},
    {"candidate_id": "CAND-002", "client_id": "C1002", "watchlist_id": deb_active["watchlist_id"],
     "signal_id": "SIG-0001", "match_method": "PAN_MISMATCH_REJECT", "confidence": 0.0,
     "decision": "REJECTED",
     "rejection_reason": f"PAN AFOPG8341M != {deb_active['pan']} -> distinct entities despite "
                         f"identical name",
     "features": {"name_similarity": 1.0, "customer_pan": "AFOPG8341M",
                  "watchlist_pan": deb_active["pan"]}},
    {"candidate_id": "CAND-003", "client_id": "C1003", "watchlist_id": saeed["watchlist_id"],
     "signal_id": "SIG-0008", "match_method": "ALIAS_BARE_REJECT", "confidence": 0.05,
     "decision": "REJECTED",
     "rejection_reason": "Matched only the bare alias 'Amir Khan' (alias_quality=bare_token). "
                         "Bare tokens require corroboration and may never trigger alone.",
     "features": {"matched_alias": "Amir Khan", "alias_quality": "bare_token",
                  "corroboration": None}},
    {"candidate_id": "CAND-004", "client_id": "C1004", "watchlist_id": pep0["watchlist_id"],
     "signal_id": None, "match_method": "CROSS_LIST_NO_LINK", "confidence": 0.30,
     "decision": "REJECTED",
     "rejection_reason": "Name appears on BOTH the Sabha PEP register and the NSE debarred list. "
                         "The two sources share zero identifiers (debarred has PAN/no DOB; Sabha "
                         "has DOB/no PAN). Auto-linking is not permitted without corroboration.",
     "features": {"name_similarity": 1.0, "pep_has_pan": False, "debarred_has_dob": False}},
    {"candidate_id": "CAND-005", "client_id": "C1005", "watchlist_id": pep0["watchlist_id"],
     "signal_id": "SIG-0004", "match_method": "NAME_EXACT", "confidence": 0.78,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"name_similarity": 1.0, "party": pep0["party"], "occupancy": "current"}},
    {"candidate_id": "CAND-006", "client_id": "C1006", "watchlist_id": rca0["watchlist_id"],
     "signal_id": None, "match_method": "NAME_EXACT", "confidence": 0.71,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"relationship": "spouse", "source": "sabha_family_graph"}},
    {"candidate_id": "CAND-007", "client_id": "C1007", "watchlist_id": saeed["watchlist_id"],
     "signal_id": "SIG-0006", "match_method": "PHONETIC", "confidence": 0.88,
     "decision": "AMBIGUOUS", "rejection_reason": None,
     "features": {"double_metaphone": "HFSMTST", "jaro_winkler": 0.91,
                  "matched_alias": saeed["aliases"][0], "alias_quality": "full_name",
                  "note": "no identifier exists on the UAPA list -> corroboration required"}},
    {"candidate_id": "CAND-008", "client_id": "C1007", "watchlist_id": saeed["watchlist_id"],
     "signal_id": "SIG-0006", "match_method": "LLM_ADJUDICATED", "confidence": 0.93,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"corroboration": "article co-mentions NIA chargesheet + designated org",
                  "llm_reasoning": "Transliteration variant confirmed by contextual "
                                   "co-occurrence with the designating authority."}},
    {"candidate_id": "CAND-009", "client_id": "C1008", "watchlist_id": deb_corp["watchlist_id"],
     "signal_id": "SIG-0007", "match_method": "PAN_EXACT", "confidence": 1.0,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"pan_match": True, "entity_type": "Corporate", "pan_4th_char": "C"}},
    {"candidate_id": "CAND-010", "client_id": "C1010", "watchlist_id": None, "signal_id": None,
     "match_method": "NO_MATCH", "confidence": 0.0, "decision": "REJECTED",
     "rejection_reason": "No candidate above blocking threshold.", "features": {}},
    {"candidate_id": "CAND-011", "client_id": "C1009", "watchlist_id": deb_revoked["watchlist_id"],
     "signal_id": "SIG-0003", "match_method": "PAN_EXACT", "confidence": 1.0,
     "decision": "CONFIRMED", "rejection_reason": None,
     "features": {"pan_match": True, "list_status": "revoked",
                  "note": "order REVOKED -> tier must DE-ESCALATE"}},
]

# ============================================================ 5. evidence + assessments
def ev(i, kind, status, claim, src, url, excerpt, conf=1.0):
    return {"evidence_id": f"EV-{i:03d}", "kind": kind, "status": status, "claim": claim,
            "source_name": src, "source_url": url, "excerpt": excerpt,
            "retrieved_at": iso(NOW), "confidence": conf}


assessments = [
    {"assessment_id": "ASM-001", "client_id": "C1001", "assessed_at": iso(NOW - timedelta(days=2)),
     "prior_tier": "NONE", "tier": "HIGH", "score": 0.71,
     "gates_fired": ["DEBARRED_PAN_EXACT_ACTIVE"], "suppressions": [],
     "contributing_signals": ["SIG-0001", "SIG-0002"], "contributing_candidates": ["CAND-001"],
     "evidence": [
         ev(1, "WATCHLIST_ENTRY", "CONFIRMED",
            f"PAN {deb_active['pan']} exactly matches an active NSE/SEBI debarment order.",
            "NSE debarred entities register",
            deb_active["source_url"][0] if deb_active["source_url"] else "",
            (deb_active["order_text"] or "")[:200]),
         ev(2, "NEWS_ARTICLE", "CONFIRMED",
            "Adverse media reports the subject was restrained by SEBI in a front-running probe.",
            "Economic Times",
            "https://economictimes.indiatimes.com/markets/example-sebi-order",
            "The regulator has restrained the subject from accessing the securities market.", 0.9),
         ev(3, "REGISTRY_RECORD", "MISSING",
            "Directorship history could not be retrieved; MCA registry lookup returned no record.",
            "MCA21 registry", "", "", 0.0),
     ],
     "explanation": "Subject's PAN exactly matches an active NSE/SEBI debarment [EV-001]. "
                    "Independent adverse media corroborates the regulatory action [EV-002]. "
                    "Directorship history could not be verified [EV-003] and is excluded from "
                    "the risk calculation."},
    {"assessment_id": "ASM-002", "client_id": "C1002", "assessed_at": iso(NOW - timedelta(days=2)),
     "prior_tier": "NONE", "tier": "NONE", "score": 0.0, "gates_fired": [],
     "suppressions": [f"PAN_MISMATCH:{deb_active['watchlist_id']}"],
     "contributing_signals": ["SIG-0001"], "contributing_candidates": ["CAND-002"],
     "evidence": [
         ev(10, "WATCHLIST_ENTRY", "CORRELATED",
            "Customer name is identical to a debarred entity, but the PANs differ.",
            "NSE debarred entities register",
            deb_active["source_url"][0] if deb_active["source_url"] else "",
            f"Customer PAN AFOPG8341M vs watchlist PAN {deb_active['pan']}.", 0.2)],
     "explanation": "No alert raised. Although the customer's name is identical to a debarred "
                    "entity, the PANs differ [EV-010], which establishes them as distinct "
                    "persons. Suppressed with reason logged."},
    {"assessment_id": "ASM-003", "client_id": "C1007", "assessed_at": iso(NOW - timedelta(days=4)),
     "prior_tier": "NONE", "tier": "CRITICAL", "score": 0.96,
     "gates_fired": ["UAPA_CONFIRMED"], "suppressions": [],
     "contributing_signals": ["SIG-0006"], "contributing_candidates": ["CAND-007", "CAND-008"],
     "evidence": [
         ev(20, "WATCHLIST_ENTRY", "CONFIRMED",
            f"Name is a listed transliteration of {saeed['name']}, designated under the Fourth "
            f"Schedule of the UAPA, 1967.",
            "MHA UAPA Fourth Schedule",
            saeed["source_url"][0] if saeed["source_url"] else "",
            f"Aliases on record: {'; '.join(saeed['aliases'][:4])}"),
         ev(21, "NEWS_ARTICLE", "CORRELATED",
            "Adverse media co-mentions the subject with the designating authority.",
            "GDELT", "https://example-news.in/terror-financing",
            "NIA names the subject in a cross-border financing chargesheet.", 0.7),
         ev(22, "INTERNAL_RECORD", "MISSING",
            "No PAN on file for this customer; the UAPA list carries no identifiers either. "
            "No identifier-level confirmation is possible.", "Internal KYC record", "", "", 0.0),
     ],
     "explanation": "CRITICAL. The customer name is a listed transliteration of a UAPA-designated "
                    "individual [EV-020], corroborated by adverse media naming the designating "
                    "authority [EV-021]. No identifier-level confirmation is possible on either "
                    "side [EV-022]; this case therefore requires human adjudication and cannot "
                    "be auto-decided in either direction."},
    {"assessment_id": "ASM-004", "client_id": "C1009", "assessed_at": iso(NOW - timedelta(days=9)),
     "prior_tier": "HIGH", "tier": "MONITOR", "score": 0.18,
     "gates_fired": ["DEBARMENT_REVOKED_DOWNGRADE"], "suppressions": [],
     "contributing_signals": ["SIG-0003"], "contributing_candidates": ["CAND-011"],
     "evidence": [
         ev(30, "WATCHLIST_ENTRY", "CONFIRMED",
            "NSE has revoked the debarment order against this subject.",
            "NSE circular (revocation)",
            deb_revoked["source_url"][0] if deb_revoked["source_url"] else "",
            "Debarment revoked per NSE circular.")],
     "explanation": "Risk DE-ESCALATED from HIGH to MONITOR. The underlying NSE debarment has "
                    "been revoked [EV-030]. The system reduces risk when the evidence base "
                    "weakens, not only when it strengthens."},
    {"assessment_id": "ASM-005", "client_id": "C1003", "assessed_at": iso(NOW - timedelta(days=5)),
     "prior_tier": "NONE", "tier": "NONE", "score": 0.0, "gates_fired": [],
     "suppressions": ["ALIAS_BARE:Amir Khan"], "contributing_signals": ["SIG-0008"],
     "contributing_candidates": ["CAND-003"],
     "evidence": [
         ev(40, "WATCHLIST_ENTRY", "CORRELATED",
            "Customer name matches a bare-token alias on the UAPA list.",
            "MHA UAPA Fourth Schedule",
            saeed["source_url"][0] if saeed["source_url"] else "",
            "'Amir Khan' is one of 97 single-token aliases; it is also an extremely common "
            "Indian name.", 0.05)],
     "explanation": "No alert raised. The only match was to the bare alias 'Amir Khan' [EV-040], "
                    "which carries alias_quality=bare_token. Bare tokens require corroboration "
                    "and may never trigger an alert on their own."},
    {"assessment_id": "ASM-006", "client_id": "C1005", "assessed_at": iso(NOW - timedelta(days=1)),
     "prior_tier": "NONE", "tier": "EDD", "score": 0.35, "gates_fired": ["PEP_CURRENT"],
     "suppressions": [], "contributing_signals": ["SIG-0004"],
     "contributing_candidates": ["CAND-005"],
     "evidence": [
         ev(50, "WATCHLIST_ENTRY", "CONFIRMED",
            f"Subject is a sitting member of Parliament ({pep0['party']}).",
            "Lok/Rajya Sabha member register", "https://sansad.in/ls/members",
            f"Current occupancy. DOB on record: {pep0['dob']}.")],
     "explanation": "EDD tier. The subject is a sitting MP [EV-050]. PEP status triggers enhanced "
                    "due diligence; it is NOT an adverse-media finding and must not be presented "
                    "as one."},
]

# ============================================================ 6. cases + SAR
sar = {
    "sar_id": "SAR-001", "case_id": "CASE-001", "drafted_at": iso(NOW - timedelta(days=3)),
    "subject_name": deb_active["name"], "subject_pan": deb_active["pan"],
    "sections": {
        "subject_identification":
            f"The subject is {deb_active['name']} (PAN {deb_active['pan']}), an individual "
            f"customer onboarded 2021-03-14 with a current exposure of INR 4.82 crore [EV-001].",
        "basis_for_suspicion":
            "The subject's PAN exactly matches an active debarment order on the NSE/SEBI "
            "debarred entities register [EV-001]. Independent adverse media reports the same "
            "regulatory action [EV-002]. The match was established on an exact identifier and "
            "did not rely on name similarity.",
        "chronology_of_events":
            f"{deb_active['order_date']}: SEBI order issued against the subject [EV-001]. "
            f"2026-07-13: adverse media reported the restraint [EV-002]. "
            f"2026-07-13: risk tier escalated NONE -> HIGH.",
        "evidence_summary":
            "CONFIRMED: PAN-level match to an active NSE/SEBI debarment [EV-001]; corroborating "
            "adverse media [EV-002]. MISSING: directorship history could not be retrieved from "
            "the MCA registry [EV-003] and has been excluded.",
        "risk_assessment":
            "Tier HIGH. Gate DEBARRED_PAN_EXACT_ACTIVE fired on a deterministic identifier match "
            "(entity-resolution confidence 1.00) [EV-001]. Soft score 0.71.",
        "recommended_action":
            "Escalate for compliance review. Recommend restriction of securities-related activity "
            "pending confirmation. Human sign-off required before filing.",
    },
    "evidence": assessments[0]["evidence"],
    "unverified_claims": [
        "The subject holds a directorship in a listed entity. — EXCLUDED: no MCA registry "
        "record was retrievable. This claim has been removed from the report.",
        "The subject is associated with the entity named in the related SEBI order. — EXCLUDED: "
        "co-accused linkage could not be confirmed at identifier level.",
    ],
    "citation_coverage": 0.96, "status": "DRAFT",
}

cases = [
    {"case_id": "CASE-001", "client_id": "C1001", "opened_at": iso(NOW - timedelta(days=2)),
     "status": "IN_REVIEW", "tier": "HIGH", "assessment_ids": ["ASM-001"],
     "timeline": [
         {"at": iso(NOW - timedelta(days=2)), "kind": "SIGNAL",
          "summary": "Adverse media: SEBI restrains subject in front-running probe.",
          "evidence_ids": ["EV-002"], "tier_before": "NONE", "tier_after": "NONE"},
         {"at": iso(NOW - timedelta(days=2, hours=-1)), "kind": "REASSESSMENT",
          "summary": "PAN exact-match to an active NSE/SEBI debarment. Gate fired.",
          "evidence_ids": ["EV-001"], "tier_before": "NONE", "tier_after": "HIGH"},
         {"at": iso(NOW - timedelta(days=1)), "kind": "SAR",
          "summary": "SAR drafted. Citation coverage 96%. 2 claims excluded as unverifiable.",
          "evidence_ids": ["EV-001", "EV-002", "EV-003"],
          "tier_before": "HIGH", "tier_after": "HIGH"},
     ],
     "sar": sar,
     "reviewer_actions": [
         {"action_id": "RA-001", "at": iso(NOW - timedelta(hours=6)), "reviewer": "analyst_priya",
          "action": "REQUEST_INFO",
          "note": "Need MCA directorship confirmation before I sign off on the SAR."}]},
    {"case_id": "CASE-002", "client_id": "C1009", "opened_at": iso(NOW - timedelta(days=400)),
     "status": "OPEN", "tier": "MONITOR", "assessment_ids": ["ASM-004"],
     "timeline": [
         {"at": iso(NOW - timedelta(days=400)), "kind": "REASSESSMENT",
          "summary": "PAN exact-match to an active NSE/SEBI debarment.",
          "evidence_ids": [], "tier_before": "NONE", "tier_after": "HIGH"},
         {"at": iso(NOW - timedelta(days=9)), "kind": "REASSESSMENT",
          "summary": "NSE revoked the debarment order. Risk DE-ESCALATED.",
          "evidence_ids": ["EV-030"], "tier_before": "HIGH", "tier_after": "MONITOR"},
     ],
     "sar": None, "reviewer_actions": []},
    {"case_id": "CASE-003", "client_id": "C1007", "opened_at": iso(NOW - timedelta(days=4)),
     "status": "ESCALATED", "tier": "CRITICAL", "assessment_ids": ["ASM-003"],
     "timeline": [
         {"at": iso(NOW - timedelta(days=4)), "kind": "SIGNAL",
          "summary": "NIA chargesheet names a transliteration of a UAPA-designated individual.",
          "evidence_ids": ["EV-021"], "tier_before": "NONE", "tier_after": "NONE"},
         {"at": iso(NOW - timedelta(days=4, hours=-1)), "kind": "REASSESSMENT",
          "summary": "UAPA gate fired. No identifier confirmation possible on either side.",
          "evidence_ids": ["EV-020", "EV-022"], "tier_before": "NONE", "tier_after": "CRITICAL"},
         {"at": iso(NOW - timedelta(days=3)), "kind": "REVIEW",
          "summary": "Escalated to MLRO. Auto-decision withheld in both directions by design.",
          "evidence_ids": [], "tier_before": "CRITICAL", "tier_after": "CRITICAL"},
     ],
     "sar": None,
     "reviewer_actions": [
         {"action_id": "RA-002", "at": iso(NOW - timedelta(days=3)), "reviewer": "analyst_priya",
          "action": "ESCALATE", "note": "UAPA. MLRO sign-off mandatory."}]},
    {"case_id": "CASE-004", "client_id": "C1002", "opened_at": iso(NOW - timedelta(days=2)),
     "status": "DISMISSED", "tier": "NONE", "assessment_ids": ["ASM-002"],
     "timeline": [
         {"at": iso(NOW - timedelta(days=2)), "kind": "REASSESSMENT",
          "summary": "Name matched a debarred entity; PANs differ. Suppressed automatically.",
          "evidence_ids": ["EV-010"], "tier_before": "NONE", "tier_after": "NONE"}],
     "sar": None,
     "reviewer_actions": [
         {"action_id": "RA-003", "at": iso(NOW - timedelta(days=1)), "reviewer": "analyst_rahul",
          "action": "DISMISS",
          "note": "Correct suppression. Confirmed distinct person. Adding a suppression rule "
                  "so this pair never re-alerts."}]},
]

# ============================================================ 7. audit
audit = []
for i, (actor, action, ot, oid, rat) in enumerate([
    ("agent:signals", "INGESTED", "Signal", "SIG-0001", "Adverse media fetched from RSS."),
    ("agent:signals", "DEDUPED", "Signal", "SIG-0002",
     "Collapsed into story_cluster_id CL-0001. One story -> one alert."),
    ("agent:er", "RESOLVED", "Candidate", "CAND-001",
     "PAN exact match. Confidence 1.00. No LLM invoked."),
    ("agent:er", "SUPPRESSED", "Candidate", "CAND-002",
     f"PAN AFOPG8341M != {deb_active['pan']}. Distinct entities. No alert raised."),
    ("agent:er", "SUPPRESSED", "Candidate", "CAND-003",
     "Bare-token alias 'Amir Khan' only. Requires corroboration."),
    ("agent:er", "SUPPRESSED", "Candidate", "CAND-004",
     "Cross-list PEP<->debarred. Zero shared identifiers. Auto-link forbidden."),
    ("agent:er", "ESCALATED_TO_LLM", "Candidate", "CAND-007",
     "Ambiguous band. Phonetic 0.88. No identifier available on the UAPA list."),
    ("agent:er", "RESOLVED", "Candidate", "CAND-008",
     "LLM adjudicated CONFIRMED on contextual corroboration."),
    ("agent:scoring", "GATE_FIRED", "RiskAssessment", "ASM-001", "DEBARRED_PAN_EXACT_ACTIVE."),
    ("agent:scoring", "GATE_FIRED", "RiskAssessment", "ASM-003",
     "UAPA_CONFIRMED. Mandatory human review. No auto-decision permitted."),
    ("agent:scoring", "DOWNGRADED", "RiskAssessment", "ASM-004",
     "Debarment revoked. HIGH -> MONITOR."),
    ("agent:investigation", "EVIDENCE_MISSING", "Evidence", "EV-003",
     "MCA registry returned no record. Marked MISSING rather than inferred."),
    ("agent:sar", "DRAFTED", "SAR", "SAR-001", "Citation coverage 0.96."),
    ("agent:sar", "CLAIM_EXCLUDED", "SAR", "SAR-001",
     "2 factual claims stripped: no resolvable Evidence id."),
    ("user:analyst_priya", "REQUEST_INFO", "Case", "CASE-001",
     "Need MCA directorship confirmation before sign-off."),
    ("user:analyst_priya", "ESCALATE", "Case", "CASE-003", "UAPA. MLRO sign-off mandatory."),
    ("user:analyst_rahul", "DISMISS", "Case", "CASE-004",
     "Correct suppression. Suppression rule added; negative example fed to ER tuning."),
    ("agent:watchlist", "DELTA", "Signal", "SIG-0003",
     "NSE revocation ingested. Zero press coverage — news-independent trigger."),
    ("agent:replay", "CLOCK_SET", "ReplayClock", "RC-001",
     "Replay 2024-01-01 -> 2026-07-01 at 1000x."),
    ("agent:signals", "TRIAGE", "Signal", "SIG-0004",
     "Committee appointment. risk_typology=[NONE]. Not adverse."),
]):
    audit.append({"audit_id": f"AUD-{i+1:03d}", "at": iso(NOW - timedelta(hours=48 - i)),
                  "actor": actor, "action": action, "object_type": ot, "object_id": oid,
                  "before": None, "after": None, "rationale": rat})

# ============================================================ write + validate
out = {"customers": customers, "watchlist": watchlist, "signals": signals,
       "candidates": candidates, "assessments": assessments, "cases": cases,
       "sar": [sar], "audit": audit}
for k, v in out.items():
    (FIX / f"{k}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))

from contracts.models import (Customer, WatchlistEntry, Signal, Candidate,
                              RiskAssessment, Case, SAR, AuditEvent)
for model, key in [(Customer, "customers"), (WatchlistEntry, "watchlist"), (Signal, "signals"),
                   (Candidate, "candidates"), (RiskAssessment, "assessments"),
                   (Case, "cases"), (SAR, "sar"), (AuditEvent, "audit")]:
    for r in out[key]:
        model(**r)
    print(f"  ok  fixtures/{key}.json  ({len(out[key])} records) validated against {model.__name__}")
print("\nAll fixtures validate against contracts/models.py")
