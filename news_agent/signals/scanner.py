"""
signals/scanner.py
------------------
Autonomous scanning loop. Orchestrates the full pipeline for each entity
on the KYC watchlist:

  1. Fetch news articles (NewsAPI)
  2. Deduplicate (skip already-seen articles via DB hash check)
  3. Entity Resolution (Stage 1 AI)
  4. Adverse Triage   (Stage 2 AI)
  5. Save signal to DB + emit downstream

This is deterministic orchestration code — NOT an agent.
The AI reasoning happens inside triage_agent.py.
"""

import os
import logging
from .models import AuditEvent
from . import emitter, kyc_list, news_fetcher, triage_agent
from .database import save_article, save_signal, append_audit, count_articles_scanned, count_signals_emitted

logger = logging.getLogger("signals.scanner")


def run_scan():
    """
    One full scan cycle across all watched entities.
    Called on a timer by the scheduler in router.py.
    """
    entities = kyc_list.get_all()

    if not entities:
        logger.warning("Watchlist is empty. Nothing to scan.")
        return

    logger.info(f"── Scan cycle started for {len(entities)} entity/entities ──")
    cycle_signals = 0

    for entity in entities:
        logger.info(f"Scanning: {entity.name}")

        append_audit(AuditEvent(
            entity_name = entity.name,
            action      = "SCAN_STARTED",
            detail      = f"Fetching news for '{entity.name}' and {len(entity.aliases)} alias(es).",
        ))

        # ── Step 1: Fetch news ────────────────────────────────────────────────
        articles = news_fetcher.fetch(
            entity_name = entity.name,
            aliases     = entity.aliases,
        )

        if not articles:
            logger.info(f"No recent news found for '{entity.name}'.")
            append_audit(AuditEvent(
                entity_name = entity.name,
                action      = "NO_NEWS_FOUND",
                detail      = "NewsAPI returned 0 results for this entity.",
            ))
            continue

        new_articles = 0
        for article in articles:

            # ── Step 2: Deduplicate ───────────────────────────────────────────
            is_new = save_article(article)
            if not is_new:
                logger.debug(f"Duplicate article skipped: '{article.headline[:60]}'")
                continue

            new_articles += 1
            append_audit(AuditEvent(
                entity_name = entity.name,
                article_id  = article.article_id,
                action      = "ARTICLE_FETCHED",
                detail      = f"Source: {article.source_name} | '{article.headline[:80]}'",
            ))

            # ── Steps 3 & 4: Entity Resolution + Triage ──────────────────────
            signal = triage_agent.analyse(article, entity)

            # ── Step 5: Save + emit ───────────────────────────────────────────
            if signal:
                save_signal(signal)
                cycle_signals += 1
                logger.info(
                    f"🚨 ADVERSE SIGNAL | {signal.entity_name} | "
                    f"{signal.severity.upper()} | {signal.confidence:.0%} | "
                    f"{signal.headline[:60]}"
                )
                # Emit downstream (CORE_API_URL -> the pipeline's /signals/ingest,
                # where the ambiguity agent verifies it against the customer book
                # and the investigation agent takes over). emit() already degrades
                # on transport failure; the guard keeps a local file error from
                # killing the whole scan cycle.
                try:
                    emitter.emit(signal)
                    append_audit(AuditEvent(
                        entity_name = signal.entity_name,
                        signal_id   = signal.signal_id,
                        action      = "SIGNAL_EMITTED",
                        detail      = f"Sent downstream to {emitter.CORE_API_URL}",
                        confidence  = signal.confidence,
                    ))
                except Exception as e:
                    logger.error(f"Emitter failed for '{signal.entity_name}': {e}")

        logger.info(f"'{entity.name}': {new_articles} new article(s) processed.")

    total_scanned = count_articles_scanned()
    total_signals = count_signals_emitted()
    logger.info(
        f"── Scan cycle complete. "
        f"Signals this cycle: {cycle_signals} | "
        f"DB totals: {total_scanned} articles scanned, {total_signals} signals emitted. ──"
    )
