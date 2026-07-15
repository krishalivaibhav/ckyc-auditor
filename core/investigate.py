"""VAIBHAV. core/investigate.py — the investigation agent.

    investigate(assessment: RiskAssessment) -> list[Evidence]

WHY THIS IS AN AGENT, NOT A GATE. The resolver's deterministic rungs confirm or
reject on IDENTIFIERS. But the lists where a miss is catastrophic carry the fewest
identifiers: adverse media has no PAN, the UAPA list has none at all. When the
ladder can only return AMBIGUOUS (or a CRITICAL case opens), there is no identifier
left to check — the only path to a confident answer is CORROBORATION. That is a
plan/execute loop, and it is what this module does:

    plan     — given the assessment + its triggering Signal + the candidate
               watchlist entry, decide what would CONFIRM or REFUTE the link:
                 * does the article name the authority that designated the entry?
                 * co-accused in the same SEBI order (order_id)?
                 * a shared relative in the Sabha family graph?
                 * does an age/DOB in the article line up with one we hold?
    execute  — gather those facts from the signal / watchlist / candidate features
    adjudicate (LLM) — weigh them and classify each as CONFIRMED / CORRELATED /
               MISSING, and reach a verdict
    emit     — list[Evidence], each carrying its status. NEVER collapse the three.

INSUFFICIENT_EVIDENCE IS A VALID ANSWER. When corroboration cannot be found the
agent returns ONLY `MISSING` (and low-confidence) evidence — it does not invent a
finding. That routes the case to human review, which is the correct outcome. An
agent that always finds something is the failure mode we are avoiding.

THE REASONING STEP USES THE ANTHROPIC API (model `claude-opus-4-8`), via a forced
tool call so the output is a validated structure. When no credentials are
configured (CI, offline demo) it degrades to a deterministic adjudicator over the
same gathered facts, so the pipeline never crashes on a missing key. Only
AMBIGUOUS / CRITICAL / EDD cases reach this function — the orchestrator gates it —
so no LLM call is ever spent on a settled deterministic match.
"""
import json
import logging
import os
import re
from pathlib import Path

from contracts.models import Evidence, RiskAssessment

log = logging.getLogger("ckyc.investigate")
FIX = Path(__file__).resolve().parents[1] / "fixtures"

MODEL = os.environ.get("CKYC_INVESTIGATE_MODEL", "claude-opus-4-8")
VERDICTS = ("CONFIRMED", "CORRELATED", "INSUFFICIENT_EVIDENCE")
STATUSES = ("CONFIRMED", "CORRELATED", "MISSING")

# Who tied an entry to its list — the authority whose name in adverse media
# corroborates (but, absent an identifier, never by itself confirms) a match.
_AUTHORITIES = {
    "MHA_UAPA": {"NIA", "MHA", "MINISTRY OF HOME AFFAIRS", "UN", "UNSC"},
    "NSE_SEBI_DEBARRED": {"SEBI", "NSE"},
    "SABHA_PEP_CURRENT": {"ECI", "LOK SABHA", "RAJYA SABHA", "PARLIAMENT"},
    "SABHA_PEP_FORMER": {"ECI", "LOK SABHA", "RAJYA SABHA", "PARLIAMENT"},
    "SABHA_RCA": {"LOK SABHA", "RAJYA SABHA", "PARLIAMENT"},
}


def _fx(name):
    return json.loads((FIX / f"{name}.json").read_text())


def _as_dict(x):
    return x if isinstance(x, dict) else x.model_dump(mode="json")


# ================================================================ gather (execute)
def _gather(assessment: RiskAssessment, sources: dict | None) -> dict:
    """Resolve the assessment's contributing signals/candidates/entries and run the
    corroboration probes. `sources` lets the caller (or a test) inject the reference
    data; by default it comes from fixtures/ (the same seam the orchestrator uses)."""
    sources = sources or {}
    sig_by_id = {s["signal_id"]: s for s in map(_as_dict, sources.get("signals") or _fx("signals"))}
    cand_by_id = {c["candidate_id"]: c for c in map(_as_dict, sources.get("candidates") or _fx("candidates"))}
    wl_by_id = {w["watchlist_id"]: w for w in map(_as_dict, sources.get("watchlist") or _fx("watchlist"))}

    signals = [sig_by_id[i] for i in assessment.contributing_signals if i in sig_by_id]
    candidates = [cand_by_id[i] for i in assessment.contributing_candidates if i in cand_by_id]
    entries, seen = [], set()   # dedupe: several candidates can point at one entry
    for c in candidates:
        wid = c.get("watchlist_id")
        if wid in wl_by_id and wid not in seen:
            seen.add(wid)
            entries.append(wl_by_id[wid])

    return {"assessment": assessment, "signals": signals,
            "candidates": candidates, "entries": entries,
            "probes": _probe(signals, entries)}


def _probe(signals: list[dict], entries: list[dict]) -> list[dict]:
    """Deterministic corroboration checks. Each check ALWAYS yields a finding: a
    hit is CORRELATED/CONFIRMED, a look-and-not-found is MISSING ('we looked'). The
    MISSING findings are the point — they are what make INSUFFICIENT_EVIDENCE an
    honest, evidenced conclusion rather than a silent shrug."""
    text = " ".join(
        (s.get("headline", "") + " " + s.get("raw_excerpt", "") + " "
         + " ".join(s.get("mentioned_orgs", []))) for s in signals).upper()
    src = signals[0] if signals else {}
    out: list[dict] = []

    if not entries:
        out.append(dict(status="MISSING", kind="INTERNAL_RECORD",
                        claim="No watchlist candidate was available to corroborate.",
                        source_name="Internal KYC record", source_url="", excerpt="",
                        confidence=0.0))
        return out

    for e in entries:
        name = e.get("name", "the subject")
        # --- probe 1: does adverse media name the designating authority?
        # Whole-word match — a substring test would let "UN" fire on "community".
        hit = sorted(a for a in _AUTHORITIES.get(e["list"], set())
                     if re.search(rf"\b{re.escape(a)}\b", text))
        if hit:
            out.append(dict(status="CORRELATED", kind="NEWS_ARTICLE",
                claim=(f"Adverse media naming the designating authority "
                       f"({', '.join(hit)}) co-occurs with a listed name for {name}."),
                source_name=src.get("source", "adverse media"),
                source_url=src.get("source_url", ""),
                excerpt=src.get("raw_excerpt", "")[:280], confidence=0.7))
        else:
            out.append(dict(status="MISSING", kind="NEWS_ARTICLE",
                claim=(f"No adverse media naming a designating authority for {name} "
                       f"was found in the triggering signal(s)."),
                source_name="Triggering signal(s)", source_url="", excerpt="",
                confidence=0.0))

        # --- probe 2: identifier-level confirmation of identity
        if e.get("pan"):
            out.append(dict(status="CONFIRMED", kind="WATCHLIST_ENTRY",
                claim=f"The {e['list']} entry carries PAN {e['pan']} for identity confirmation.",
                source_name="Watchlist entry",
                source_url=(e.get("source_url") or [""])[0], excerpt="", confidence=1.0))
        else:
            out.append(dict(status="MISSING", kind="INTERNAL_RECORD",
                claim=(f"The {e['list']} entry carries no identifier (PAN/DOB); "
                       f"no identifier-level confirmation of identity is possible."),
                source_name="Internal KYC record", source_url="", excerpt="",
                confidence=0.0))

        # --- probe 3: co-accused in the same regulatory order
        if e.get("order_id") and any(o is not e and o.get("order_id") == e["order_id"]
                                     for o in entries):
            out.append(dict(status="CORRELATED", kind="WATCHLIST_ENTRY",
                claim=f"{name} is co-accused with another entity in order {e['order_id']}.",
                source_name="Co-accused order graph", source_url="", excerpt="",
                confidence=0.6))
        else:
            out.append(dict(status="MISSING", kind="WATCHLIST_ENTRY",
                claim=(f"No shared regulatory order links {name} to the customer "
                       f"({e['list']} carries no order identifier to check)."),
                source_name="Co-accused order graph", source_url="", excerpt="",
                confidence=0.0))

    return out


# ================================================================ adjudicate (plan)
def _offline_adjudicate(ctx: dict) -> dict:
    """Deterministic stand-in for the LLM reasoning step (used with no API key).
    Verdict follows the strongest finding; if nothing corroborates, it is honestly
    INSUFFICIENT_EVIDENCE and only MISSING findings are emitted."""
    findings = [{k: p[k] for k in
                 ("status", "claim", "source_name", "source_url", "excerpt", "confidence", "kind")}
                for p in ctx["probes"]]
    if any(f["status"] == "CONFIRMED" for f in findings):
        verdict = "CONFIRMED"
    elif any(f["status"] == "CORRELATED" for f in findings):
        verdict = "CORRELATED"
    else:
        verdict = "INSUFFICIENT_EVIDENCE"
    return {"verdict": verdict, "findings": findings}


_TOOL = {
    "name": "record_investigation",
    "description": "Record the corroboration findings and the overall verdict.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": list(VERDICTS),
                        "description": "INSUFFICIENT_EVIDENCE if nothing corroborates identity."},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": list(STATUSES)},
                        "claim": {"type": "string"},
                        "source_name": {"type": "string"},
                        "source_url": {"type": "string"},
                        "excerpt": {"type": "string"},
                        "confidence": {"type": "number"},
                        "kind": {"type": "string",
                                 "enum": ["WATCHLIST_ENTRY", "NEWS_ARTICLE",
                                          "REGISTRY_RECORD", "INTERNAL_RECORD"]},
                    },
                    "required": ["status", "claim", "confidence", "kind"],
                },
            },
        },
        "required": ["verdict", "findings"],
    },
}

_SYSTEM = (
    "You are a KYC investigation agent. A deterministic resolver has left a match "
    "AMBIGUOUS or opened a CRITICAL case; there is no identifier to confirm identity, "
    "so your job is to weigh CORROBORATION only. Classify each fact as CONFIRMED "
    "(identifier-level proof), CORRELATED (suggestive, e.g. the designating authority "
    "is named but no identifier), or MISSING (you looked and it is not there). If "
    "nothing corroborates identity, return verdict INSUFFICIENT_EVIDENCE and emit only "
    "MISSING/low-confidence findings — DO NOT invent a finding. Never collapse the "
    "three statuses. Call record_investigation exactly once."
)


def _llm_adjudicate(ctx: dict) -> dict:
    """The reasoning step: hand the gathered facts to Claude and force a structured
    verdict via tool use. Raises on any client/validation failure so the caller can
    fall back to the deterministic adjudicator."""
    import anthropic

    a = ctx["assessment"]
    payload = {
        "tier": a.tier, "explanation": a.explanation,
        "candidates": [{"match_method": c.get("match_method"), "decision": c.get("decision"),
                        "features": c.get("features", {})} for c in ctx["candidates"]],
        "watchlist_entries": [{"list": e["list"], "name": e["name"],
                               "aliases": e.get("aliases", []), "has_pan": bool(e.get("pan")),
                               "order_id": e.get("order_id")} for e in ctx["entries"]],
        "triggering_signals": [{"headline": s.get("headline"), "excerpt": s.get("raw_excerpt"),
                                "orgs": s.get("mentioned_orgs", []), "source": s.get("source"),
                                "source_url": s.get("source_url")} for s in ctx["signals"]],
        "deterministic_probes": ctx["probes"],
    }
    resp = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=1024, system=_SYSTEM,
        tools=[_TOOL], tool_choice={"type": "tool", "name": "record_investigation"},
        messages=[{"role": "user",
                   "content": "Investigate this potential match:\n"
                              + json.dumps(payload, ensure_ascii=False, indent=1)}])
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_investigation":
            data = block.input
            if (data.get("verdict") in VERDICTS
                    and all(f.get("status") in STATUSES for f in data.get("findings", []))):
                return data
            raise ValueError(f"adjudicator returned an off-schema result: {data!r}")
    raise ValueError("adjudicator did not call record_investigation")


def _default_adjudicator(ctx: dict) -> dict:
    """Anthropic reasoning when a key is configured; deterministic fallback otherwise."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _llm_adjudicate(ctx)
        except Exception as e:   # noqa: BLE001 — degrade, never crash the pipeline
            log.warning("LLM adjudication failed (%s); using deterministic fallback", e)
    return _offline_adjudicate(ctx)


# ================================================================ emit
def _to_evidence(result: dict, ctx: dict) -> list[Evidence]:
    ts = ctx["assessment"].assessed_at
    out = []
    for i, f in enumerate(result.get("findings", []), 1):
        out.append(Evidence(
            evidence_id=f"EV-INV-{i:03d}", kind=f.get("kind", "INTERNAL_RECORD"),
            status=f["status"], claim=f["claim"],
            source_name=f.get("source_name") or "n/a", source_url=f.get("source_url") or "",
            excerpt=f.get("excerpt") or "", retrieved_at=ts,
            confidence=float(f.get("confidence", 0.0))))
    return out


def investigate(assessment: RiskAssessment, *, adjudicate=None, sources=None) -> list[Evidence]:
    """Corroborate an AMBIGUOUS/CRITICAL match and return an Evidence chain.

    Returns only MISSING / low-confidence Evidence when corroboration cannot be
    found — i.e. it CAN conclude INSUFFICIENT_EVIDENCE rather than invent a finding.
    `adjudicate` (a callable ctx -> {verdict, findings}) overrides the reasoning step,
    for tests or an alternative model.
    """
    ctx = _gather(assessment, sources)
    result = (adjudicate or _default_adjudicator)(ctx)
    return _to_evidence(result, ctx)
