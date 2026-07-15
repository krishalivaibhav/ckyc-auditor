"""
signals/news_fetcher.py
-----------------------
Fetches recent news articles from NewsAPI with:
  - Retry logic (up to 3 attempts with exponential backoff)
  - Deduplication via SHA-256 content hash
  - Input sanitisation before sending to external API
  - Timeout enforcement
  - Structured logging
"""

import os
import hashlib
import logging
import time
import requests
from datetime import datetime, timedelta, timezone
from .models import RawArticle
from .security import sanitise

logger = logging.getLogger("signals.news_fetcher")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BASE_URL     = "https://newsapi.org/v2/everything"
TIMEOUT_SEC  = 10
MAX_RETRIES  = 3

# High-quality Indian & global financial news domains
PREFERRED_DOMAINS = (
    "economictimes.indiatimes.com,"
    "moneycontrol.com,"
    "livemint.com,"
    "business-standard.com,"
    "thehindu.com,"
    "ndtv.com,"
    "reuters.com,"
    "bloomberg.com,"
    "hindustantimes.com"
)


def _make_content_hash(headline: str, url: str) -> str:
    """SHA-256 hash of headline+url — uniquely identifies an article for deduplication."""
    raw = f"{headline.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _fetch_with_retry(params: dict) -> list[dict]:
    """
    Call NewsAPI with exponential backoff on transient failures.
    Returns empty list on permanent failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=TIMEOUT_SEC)

            if response.status_code == 200:
                return response.json().get("articles", [])

            if response.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"NewsAPI rate-limited. Waiting {wait}s before retry {attempt}.")
                time.sleep(wait)
                continue

            if response.status_code == 401:
                logger.error("NewsAPI: Invalid API key. Check NEWS_API_KEY in .env.")
                return []

            logger.warning(f"NewsAPI returned {response.status_code} on attempt {attempt}.")

        except requests.Timeout:
            logger.warning(f"NewsAPI timed out on attempt {attempt}/{MAX_RETRIES}.")
        except requests.RequestException as e:
            logger.error(f"NewsAPI request failed: {e}")
            return []

        time.sleep(2 ** attempt)   # exponential backoff

    logger.error("NewsAPI: All retry attempts exhausted.")
    return []


def fetch(entity_name: str, aliases: list[str] = [], days_back: int = 7) -> list[RawArticle]:
    """
    Fetch recent news articles about an entity.

    Args:
        entity_name : Primary name to search (e.g. "Adani Group")
        aliases     : Additional search terms (e.g. ["Adani Enterprises"])
        days_back   : How many days of news to retrieve (max 30 on free tier)

    Returns:
        List of RawArticle objects, deduplicated by content hash.
    """
    if not NEWS_API_KEY:
        logger.error("NEWS_API_KEY not set. Skipping news fetch.")
        return []

    # Sanitise before building the query — prevents prompt injection into the URL
    safe_name    = sanitise(entity_name, max_length=100)
    safe_aliases = [sanitise(a, max_length=100) for a in aliases if a.strip()]

    all_terms = [safe_name] + safe_aliases
    query     = " OR ".join(f'"{t}"' for t in all_terms if t)
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "q":        query,
        "from":     from_date,
        "sortBy":   "publishedAt",
        "language": "en",
        "domains":  PREFERRED_DOMAINS,
        "pageSize": 10,
        "apiKey":   NEWS_API_KEY,
    }

    raw_articles = _fetch_with_retry(params)
    logger.info(f"NewsAPI returned {len(raw_articles)} article(s) for '{safe_name}'.")

    results: list[RawArticle] = []
    seen_hashes: set[str] = set()

    for item in raw_articles:
        headline = (item.get("title") or "").strip()
        url      = (item.get("url") or "").strip()

        if not headline or not url or "[Removed]" in headline:
            continue

        content_hash = _make_content_hash(headline, url)

        # Skip within-batch duplicates
        if content_hash in seen_hashes:
            logger.debug(f"Skipping duplicate article: '{headline[:60]}'")
            continue
        seen_hashes.add(content_hash)

        results.append(RawArticle(
            entity_name  = entity_name,
            headline     = headline,
            description  = (item.get("description") or "")[:1000],
            url          = url,
            source_name  = item.get("source", {}).get("name", "Unknown"),
            published_at = item.get("publishedAt", datetime.now(timezone.utc).isoformat()),
            content_hash = content_hash,
        ))

    return results
