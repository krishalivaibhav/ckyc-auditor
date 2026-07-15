"""
signals/scanner.py
------------------
The autonomous scanning loop.

Every N minutes (configurable via SCAN_INTERVAL_MINUTES env var), it:
  1. Reads every entity from the KYC watchlist.
  2. Fetches recent news for each entity via NewsAPI.
  3. Passes each article through the LLM Triage Agent.
  4. Emits a Signal for every article the LLM confirms as genuinely adverse.

This is plain code, not an "agent" — APScheduler handles the timing.
The actual AI reasoning happens inside triage_agent.py.
"""

import os
from signals import kyc_list, news_fetcher, triage_agent, emitter

SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))


def run_scan():
    """
    One full scan cycle: fetch news for all watched entities and triage each article.
    Called by the APScheduler on a configurable interval.
    """
    entities = kyc_list.get_all()

    if not entities:
        print("[Scanner] Watchlist is empty. Nothing to scan.")
        return

    print(f"\n[Scanner] ── Starting scan cycle for {len(entities)} entity/entities ──")

    total_signals = 0

    for entity in entities:
        print(f"[Scanner] Scanning: {entity.name}")

        # 1. Fetch news articles from NewsAPI
        articles = news_fetcher.NewsFetcher.fetch(
            entity_name=entity.name,
            aliases=entity.aliases,
        )

        if not articles:
            print(f"[Scanner] No recent news found for '{entity.name}'. Skipping.")
            continue

        # 2. Triage each article through the LLM agent
        for article in articles:
            signal = triage_agent.triage(
                entity_name=entity.name,
                article=article,
            )

            # 3. If the LLM confirms it is adverse → emit it downstream
            if signal:
                emitter.emit(signal)
                total_signals += 1

    print(f"[Scanner] ── Scan cycle complete. {total_signals} adverse signal(s) emitted. ──\n")
