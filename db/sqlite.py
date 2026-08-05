"""
SQLite connection module — single source of truth for the local database.

The database file lives at  data/tracker.db  (relative to the project root).
Both the collector pipeline and the FastAPI server import from here.
"""

import json
import os
import sqlite3
from pathlib import Path

# Resolve project root regardless of where the script is called from
_PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = _PROJECT_ROOT / "data" / "tracker.db"


def get_conn() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set to dict-like rows."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safe for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict, deserialising JSON columns."""
    if row is None:
        return {}
    d = dict(row)
    for key, value in d.items():
        if isinstance(value, str) and value.startswith("["):
            try:
                d[key] = json.loads(value)
            except Exception:
                pass
    return d


def rows_to_dicts(rows) -> list[dict]:
    return [row_to_dict(r) for r in rows]


def init_db():
    """Create all tables if they don't already exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS domains (
        id          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_name TEXT NOT NULL UNIQUE,
        display_name TEXT,
        client_id   TEXT,
        is_active   INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS keyword_volumes (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        keyword         TEXT NOT NULL UNIQUE,
        monthly_volume  INTEGER NOT NULL DEFAULT 0,
        competition     TEXT NOT NULL DEFAULT 'MEDIUM',
        updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS tech_profiles (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id       TEXT NOT NULL REFERENCES domains(id),
        detected_tech   TEXT NOT NULL DEFAULT '[]',
        scan_status     TEXT NOT NULL DEFAULT 'success',
        scraped_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS keyword_rankings (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id       TEXT NOT NULL REFERENCES domains(id),
        keyword         TEXT NOT NULL,
        rank_position   INTEGER,
        checked_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS traffic_estimates (
        id                          TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id                   TEXT NOT NULL REFERENCES domains(id),
        keyword                     TEXT NOT NULL,
        monthly_search_volume       INTEGER NOT NULL DEFAULT 0,
        serp_rank                   INTEGER,
        estimated_ctr               REAL NOT NULL DEFAULT 0,
        estimated_monthly_visits    INTEGER NOT NULL DEFAULT 0,
        estimated_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS sitemap_metrics (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id       TEXT NOT NULL REFERENCES domains(id),
        total_pages     INTEGER NOT NULL DEFAULT 0,
        last_modified   TEXT,
        scanned_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS site_changes (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id       TEXT NOT NULL REFERENCES domains(id),
        page_url        TEXT NOT NULL,
        html_hash       TEXT NOT NULL,
        has_changed     INTEGER NOT NULL DEFAULT 0,
        checked_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );

    CREATE TABLE IF NOT EXISTS scan_errors (
        id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        domain_id       TEXT REFERENCES domains(id),
        module          TEXT NOT NULL,
        error_type      TEXT NOT NULL,
        error_message   TEXT NOT NULL,
        occurred_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    );
    """
    with get_conn() as conn:
        conn.executescript(schema)
