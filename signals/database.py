"""
signals/database.py
-------------------
SQLite database layer. Saves every article seen, every AI decision made,
and every adverse signal emitted — permanently and in full.

Problem Statement requirement:
  "Maintain a human-review workflow and audit trail for alerts,
   evidence, AI decisions, and reviewer actions."

Uses SQLite so there is ZERO setup required — no Postgres, no Docker needed
for standalone testing. Just runs as a file on disk.
"""

import sqlite3
import json
import os
from pathlib import Path
from signals.models import RawArticle, Signal, AuditEvent, EntityResolution

DB_PATH = Path(os.getenv("DB_PATH", "signals/signals.db"))


def _get_conn() -> sqlite3.Connection:
    """Get a thread-safe SQLite connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # write-ahead logging — safer
    return conn


def init_db():
    """Create all tables on startup if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlist (
            entity_id   TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            aliases     TEXT,           -- JSON array
            entity_type TEXT,
            country     TEXT,
            sector      TEXT,
            notes       TEXT,
            added_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS raw_articles (
            article_id    TEXT PRIMARY KEY,
            entity_name   TEXT NOT NULL,
            headline      TEXT NOT NULL,
            description   TEXT,
            url           TEXT NOT NULL,
            source_name   TEXT,
            published_at  TEXT,
            fetched_at    TEXT,
            content_hash  TEXT UNIQUE,   -- prevents duplicate articles
            processed     INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS entity_resolutions (
            article_id   TEXT PRIMARY KEY,
            entity_name  TEXT,
            verdict      TEXT,
            confidence   REAL,
            evidence     TEXT,
            resolved_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS signals (
            signal_id        TEXT PRIMARY KEY,
            entity_name      TEXT NOT NULL,
            headline         TEXT NOT NULL,
            url              TEXT NOT NULL,
            source_name      TEXT,
            published_at     TEXT,
            detected_at      TEXT,
            severity         TEXT,
            confidence       REAL,
            triage_reasoning TEXT,
            er_reasoning     TEXT,
            status           TEXT DEFAULT 'emitted'
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            event_id    TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            entity_name TEXT,
            article_id  TEXT,
            signal_id   TEXT,
            action      TEXT NOT NULL,
            detail      TEXT,
            confidence  REAL
        );
    """)
    conn.commit()
    conn.close()


# ── Write operations ──────────────────────────────────────────────────────────

def save_article(article: RawArticle) -> bool:
    """
    Save a raw article. Returns False if it already exists (deduplicated).
    """
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO raw_articles
            (article_id, entity_name, headline, description, url,
             source_name, published_at, fetched_at, content_hash)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            article.article_id, article.entity_name, article.headline,
            article.description, article.url, article.source_name,
            article.published_at, article.fetched_at, article.content_hash,
        ))
        inserted = conn.total_changes > 0
        conn.commit()
        return inserted
    finally:
        conn.close()


def save_resolution(resolution: EntityResolution):
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO entity_resolutions
            (article_id, entity_name, verdict, confidence, evidence, resolved_at)
            VALUES (?,?,?,?,?,?)
        """, (
            resolution.article_id, resolution.entity_name,
            resolution.verdict, resolution.confidence,
            resolution.evidence, resolution.resolved_at,
        ))
        conn.commit()
    finally:
        conn.close()


def save_signal(signal: Signal):
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO signals
            (signal_id, entity_name, headline, url, source_name,
             published_at, detected_at, severity, confidence,
             triage_reasoning, er_reasoning, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            signal.signal_id, signal.entity_name, signal.headline,
            signal.url, signal.source_name, signal.published_at,
            signal.detected_at, signal.severity, signal.confidence,
            signal.triage_reasoning, signal.er_reasoning, signal.status,
        ))
        conn.commit()
    finally:
        conn.close()


def append_audit(event: AuditEvent):
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO audit_log
            (event_id, timestamp, entity_name, article_id,
             signal_id, action, detail, confidence)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            event.event_id, event.timestamp, event.entity_name,
            event.article_id, event.signal_id, event.action,
            event.detail, event.confidence,
        ))
        conn.commit()
    finally:
        conn.close()


# ── Read operations ───────────────────────────────────────────────────────────

def get_all_signals() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY detected_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_audit_log(limit: int = 100) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_signals_for_entity(entity_name: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM signals WHERE entity_name=? ORDER BY detected_at DESC",
            (entity_name,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_articles_scanned() -> int:
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM raw_articles").fetchone()[0]
    finally:
        conn.close()


def count_signals_emitted() -> int:
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    finally:
        conn.close()
