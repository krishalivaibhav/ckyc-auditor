"""
signals/triage_agent.py
-----------------------
The core AI Agent of the signals package.

Uses Google Gemini (free tier) to judge whether a news article is
genuinely ADVERSE to a watched entity.

This solves the false-positive problem. Example:
  "Infosys is fighting against fraud"  → NOT adverse (suppressed)
  "Adani Group director arrested for fraud" → ADVERSE / HIGH (emitted)

The LLM reads full context, not just keywords.
"""

import os
import json
import google.generativeai as genai
from signals.models import Signal, Severity
from datetime import datetime, timezone


# Configure Gemini with the API key from environment
genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = genai.GenerativeModel("gemini-1.5-flash")   # free, fast, capable

TRIAGE_PROMPT = """
You are a senior KYC compliance analyst at an Indian bank.

Your job is to read a news article headline and description about a corporate entity
and decide whether it is GENUINELY ADVERSE to that entity from a financial compliance
and regulatory risk perspective.

ADVERSE means: fraud, scam, money laundering, regulatory fine, SEC/SEBI/RBI action,
criminal charges, sanctions, terrorist financing, bribery, corruption, arrest,
insolvency/bankruptcy triggered by misconduct, or major reputational damage.

NOT ADVERSE means: the company is fighting AGAINST fraud, winning a legal case,
reporting third-party fraud (as a victim), general market news, earnings reports,
leadership changes with no misconduct angle, or unrelated mentions.

Entity being monitored: {entity_name}
Article Headline: {headline}
Article Description: {description}
Published At: {published_at}
Source URL: {url}

Respond ONLY with a valid JSON object in this exact format, no extra text:
{{
  "is_adverse": true or false,
  "severity": "low" or "medium" or "high",
  "confidence": a float between 0.0 and 1.0,
  "reasoning": "one or two sentences explaining your decision in plain English"
}}

Rules:
- If is_adverse is false, still populate severity as "low" and give a short reasoning.
- Confidence above 0.85 means you are very sure. Below 0.6 means borderline.
- Never flag an article adverse just because it contains risk keywords — read the CONTEXT.
"""


def triage(entity_name: str, article: dict) -> Signal | None:
    """
    Runs the Gemini triage agent on a single article.

    Args:
        entity_name: The name of the watched entity this article is about.
        article: Raw article dict from NewsAPI (title, description, url, publishedAt).

    Returns:
        A Signal object if the article is genuinely adverse.
        None if NOT adverse or if triage fails.
    """
    headline    = article.get("title", "")
    description = article.get("description") or article.get("content") or ""
    url         = article.get("url", "")
    published_at = article.get("publishedAt", datetime.now(timezone.utc).isoformat())

    # Skip articles with no useful content
    if not headline or not url:
        return None

    prompt = TRIAGE_PROMPT.format(
        entity_name=entity_name,
        headline=headline,
        description=description,
        published_at=published_at,
        url=url,
    )

    try:
        response = _model.generate_content(prompt)
        raw = response.text.strip()

        # Gemini sometimes wraps JSON in markdown code fences — strip them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        verdict      = json.loads(raw)
        is_adverse   = verdict.get("is_adverse", False)
        confidence   = float(verdict.get("confidence", 0.0))
        reasoning    = verdict.get("reasoning", "No reasoning provided.")
        severity_str = verdict.get("severity", "low")

        print(
            f"[TriageAgent] '{entity_name}' | adverse={is_adverse} | "
            f"confidence={confidence:.0%} | '{headline[:60]}...'"
        )

        # Only emit a Signal if genuinely adverse AND confident enough
        if is_adverse and confidence >= 0.70:
            return Signal(
                entity_name=entity_name,
                headline=headline,
                url=url,
                source=article.get("source", {}).get("name", "NewsAPI"),
                published_at=published_at,
                detected_at=datetime.now(timezone.utc).isoformat(),
                severity=Severity(severity_str),
                triage_reasoning=reasoning,
                confidence=confidence,
            )

        return None

    except json.JSONDecodeError as e:
        print(f"[TriageAgent] ERROR: Gemini returned invalid JSON for '{entity_name}': {e}")
        return None
    except Exception as e:
        print(f"[TriageAgent] ERROR during triage for '{entity_name}': {e}")
        return None
