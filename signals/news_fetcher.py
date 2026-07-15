"""
signals/news_fetcher.py
-----------------------
Fetches news articles about a given entity from NewsAPI.org.

NewsAPI free tier:
  - 100 requests / day
  - 1 month of historical articles
  - Requires API key (set NEWS_API_KEY in .env)

Usage:
    articles = NewsFetcher.fetch("Adani Group")
"""

import os
import requests
from datetime import datetime, timedelta


class NewsFetcher:
    BASE_URL = "https://newsapi.org/v2/everything"
    API_KEY = os.getenv("NEWS_API_KEY", "")

    # Domains that are known to be high-quality Indian financial news sources
    # This dramatically improves signal quality vs. searching the whole internet
    PREFERRED_DOMAINS = (
        "economictimes.indiatimes.com,"
        "moneycontrol.com,"
        "livemint.com,"
        "business-standard.com,"
        "thehindu.com,"
        "ndtv.com,"
        "reuters.com,"
        "bloomberg.com"
    )

    @classmethod
    def fetch(cls, entity_name: str, aliases: list[str] = [], days_back: int = 7) -> list[dict]:
        """
        Search NewsAPI for recent articles about an entity.

        Args:
            entity_name: Primary name to search for.
            aliases: Additional search terms (e.g. "Infy" for "Infosys").
            days_back: How many days back to search (default: last 7 days).

        Returns:
            A list of raw article dicts from NewsAPI (headline, url, publishedAt, description).
            Returns [] on failure so callers never crash.
        """
        if not cls.API_KEY:
            print("[NewsFetcher] WARNING: NEWS_API_KEY not set. Returning empty results.")
            return []

        # Build the search query: "Adani Group" OR "Adani Enterprises" OR "Adani Ports"
        all_terms = [entity_name] + aliases
        query = " OR ".join(f'"{term}"' for term in all_terms)

        # Date range: from N days ago to today
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",     # most recent first
            "language": "en",
            "domains": cls.PREFERRED_DOMAINS,
            "pageSize": 10,              # top 10 articles per entity per scan
            "apiKey": cls.API_KEY,
        }

        try:
            response = requests.get(cls.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            articles = data.get("articles", [])
            print(f"[NewsFetcher] Found {len(articles)} article(s) for '{entity_name}'.")
            return articles

        except requests.RequestException as e:
            print(f"[NewsFetcher] ERROR fetching news for '{entity_name}': {e}")
            return []
