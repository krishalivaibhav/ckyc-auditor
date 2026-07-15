"""
signals/triage_agent.py
-----------------------
Two-stage AI pipeline per the problem statement:

STAGE 1 — Entity Resolution (ER):
  "Use semantic analysis and entity-resolution logic to reduce false positives,
   such as separating a corporate director from an unrelated person with the
   same name." — Problem Statement

STAGE 2 — Adverse Media Triage:
  "Create an adverse media and sanctions monitoring agent that checks news
   sources... Use semantic analysis... to reduce false positives." — Problem Statement

Both stages use Groq (Llama 3.3 70B) — free, fast, and accurate.
Temperature is set LOW (0.1) for deterministic, consistent outputs.
"""

import os
import json
import time
import logging
from groq import Groq
from .models import RawArticle, EntityResolution, Signal, AuditEvent, MatchVerdict, Severity
from .database import save_resolution, append_audit
from .security import sanitise
from datetime import datetime, timezone

logger = logging.getLogger("signals.triage_agent")

_client   = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL    = "llama-3.3-70b-versatile"
_TEMP     = 0.1   # low = deterministic, consistent


# ── Stage 1: Entity Resolution ────────────────────────────────────────────────

_ER_PROMPT = """You are a KYC entity-resolution specialist at an Indian bank.

We are monitoring an entity named: "{entity_name}"
Entity type: {entity_type}
Country: {country}

We found a news article. Decide if this article is about OUR specific entity,
or about a different entity that merely shares a similar name.

Article headline : {headline}
Article text     : {description}
News source      : {source_name}

Respond ONLY with valid JSON — no extra text, no markdown:
{{"verdict": "confirmed" | "false_positive" | "needs_review",
  "confidence": 0.0 to 1.0,
  "evidence": "One sentence: which specific details in the article match or mismatch our entity."}}

Rules:
- "confirmed"      : The article is clearly about our monitored entity (confidence > 0.75)
- "false_positive" : The article is about a different entity with a similar name (confidence > 0.75)
- "needs_review"   : You cannot determine this with confidence — send to human
- Be strict: only say confirmed if there is real evidence linking the article to our entity
- Country, sector, role, and co-occurring names are strong evidence"""


def run_entity_resolution(article: RawArticle, entity) -> EntityResolution:
    """
    Stage 1: Determine if the article is about the watched entity or a different one.
    """
    prompt = _ER_PROMPT.format(
        entity_name = sanitise(article.entity_name),
        entity_type = getattr(entity, "entity_type", "company"),
        country     = getattr(entity, "country", "IN"),
        headline    = sanitise(article.headline, 300),
        description = sanitise(article.description, 800),
        source_name = sanitise(article.source_name, 100),
    )

    try:
        response = _client.chat.completions.create(
            model       = _MODEL,
            messages    = [{"role": "user", "content": prompt}],
            max_tokens  = 200,
            temperature = _TEMP,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        data       = json.loads(raw)
        verdict    = MatchVerdict(data.get("verdict", "needs_review"))
        confidence = float(data.get("confidence", 0.5))
        evidence   = data.get("evidence", "No evidence provided.")

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[ER] Error for '{article.entity_name}': {e}")
        verdict    = MatchVerdict.needs_review
        confidence = 0.0
        evidence   = f"ER agent error: {type(e).__name__}"

    resolution = EntityResolution(
        article_id  = article.article_id,
        entity_name = article.entity_name,
        verdict     = verdict,
        confidence  = confidence,
        evidence    = evidence,
    )

    save_resolution(resolution)
    append_audit(AuditEvent(
        entity_name = article.entity_name,
        article_id  = article.article_id,
        action      = f"ER_{verdict.upper()}",
        detail      = evidence,
        confidence  = confidence,
    ))

    logger.info(
        f"[ER] '{article.entity_name}' | verdict={verdict} | "
        f"confidence={confidence:.0%} | '{article.headline[:50]}...'"
    )
    return resolution


# ── Stage 2: Adverse Media Triage ─────────────────────────────────────────────

_TRIAGE_PROMPT = """You are a senior KYC compliance analyst at an Indian bank.

An article has been confirmed to be about our monitored entity: "{entity_name}"

Determine if this article represents GENUINE ADVERSE MEDIA from a compliance
and regulatory risk perspective.

ADVERSE (flag it):
  Fraud, scam, money laundering, bribery, corruption, SEBI/RBI/CBI/ED action,
  criminal charges, arrest, sanction, terrorism financing, market manipulation,
  insider trading, insolvency due to misconduct, reputational scandal.

NOT ADVERSE (suppress it):
  Company fighting against or reporting fraud as a victim, winning a legal case,
  general business news, earnings, partnerships, product launches, price changes.

Article headline : {headline}
Article text     : {description}
Source           : {source_name}
Published        : {published_at}

Respond ONLY with valid JSON — no extra text, no markdown:
{{"is_adverse": true | false,
  "severity": "low" | "medium" | "high" | "critical",
  "confidence": 0.0 to 1.0,
  "reasoning": "One to two sentences: exactly why this IS or IS NOT adverse."}}

Severity guide:
  critical — UAPA/terrorism, sanctions hit, confirmed criminal conviction
  high     — Regulatory bar/fine, arrest, active ED/CBI investigation
  medium   — Adverse media report, SEBI notice, court summons
  low      — Unverified allegation or minor compliance flag"""


def run_triage(article: RawArticle, er_reasoning: str) -> Signal | None:
    """
    Stage 2: Semantic adverse media analysis.
    Only called when Entity Resolution returns 'confirmed'.
    Returns a Signal if adverse, None if benign.
    """
    prompt = _TRIAGE_PROMPT.format(
        entity_name = sanitise(article.entity_name),
        headline    = sanitise(article.headline, 300),
        description = sanitise(article.description, 800),
        source_name = sanitise(article.source_name, 100),
        published_at = article.published_at,
    )

    try:
        response = _client.chat.completions.create(
            model       = _MODEL,
            messages    = [{"role": "user", "content": prompt}],
            max_tokens  = 256,
            temperature = _TEMP,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        data        = json.loads(raw)
        is_adverse  = bool(data.get("is_adverse", False))
        severity    = Severity(data.get("severity", "low"))
        confidence  = float(data.get("confidence", 0.0))
        reasoning   = data.get("reasoning", "No reasoning provided.")

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[Triage] Error for '{article.entity_name}': {e}")
        return None

    action = "TRIAGED_ADVERSE" if is_adverse and confidence >= 0.70 else "TRIAGED_BENIGN"
    append_audit(AuditEvent(
        entity_name = article.entity_name,
        article_id  = article.article_id,
        action      = action,
        detail      = reasoning,
        confidence  = confidence,
    ))

    logger.info(
        f"[Triage] '{article.entity_name}' | adverse={is_adverse} | "
        f"severity={severity} | confidence={confidence:.0%} | "
        f"'{article.headline[:50]}...'"
    )

    if is_adverse and confidence >= 0.70:
        return Signal(
            entity_name      = article.entity_name,
            headline         = article.headline,
            url              = article.url,
            source_name      = article.source_name,
            published_at     = article.published_at,
            severity         = severity,
            confidence       = confidence,
            triage_reasoning = reasoning,
            er_reasoning     = er_reasoning,
        )

    return None


# ── Combined pipeline ─────────────────────────────────────────────────────────

def analyse(article: RawArticle, entity) -> Signal | None:
    """
    Full two-stage analysis pipeline:
      1. Entity Resolution → confirm the article is about our entity
      2. Adverse Triage   → confirm the news is genuinely bad

    Returns a Signal if both stages pass, None otherwise.
    """
    # Add a small delay between LLM calls to avoid rate-limit bursts
    time.sleep(0.5)

    # Stage 1
    resolution = run_entity_resolution(article, entity)

    if resolution.verdict == MatchVerdict.false_positive:
        logger.info(f"[Pipeline] SUPPRESSED (false positive): '{article.headline[:60]}'")
        append_audit(AuditEvent(
            entity_name = article.entity_name,
            article_id  = article.article_id,
            action      = "SUPPRESSED_FALSE_POSITIVE",
            detail      = resolution.evidence,
            confidence  = resolution.confidence,
        ))
        return None

    if resolution.verdict == MatchVerdict.needs_review:
        logger.info(f"[Pipeline] ESCALATED to human review: '{article.headline[:60]}'")
        return None   # Human review queue handled by core/

    # Stage 2 (only if ER says confirmed)
    time.sleep(0.5)
    return run_triage(article, er_reasoning=resolution.evidence)
