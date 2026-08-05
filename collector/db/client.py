"""SQLite client for the collector pipeline."""

import json
import uuid
from db.sqlite import get_conn, rows_to_dicts, row_to_dict


def get_active_domains() -> list[dict]:
    """Return all active domains."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM domains WHERE is_active = 1"
        ).fetchall()
    return rows_to_dicts(rows)


def get_keyword_volumes() -> dict[str, int]:
    """Return {keyword: monthly_volume} mapping."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT keyword, monthly_volume FROM keyword_volumes"
        ).fetchall()
    return {row["keyword"]: row["monthly_volume"] for row in rows}


def upsert_tech_profile(domain_id: str, detected_tech: list, scan_status: str = "success") -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tech_profiles (id, domain_id, detected_tech, scan_status)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, json.dumps(detected_tech), scan_status),
        )


def upsert_keyword_ranking(domain_id: str, keyword: str, rank_position: int | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO keyword_rankings (id, domain_id, keyword, rank_position)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, keyword, rank_position),
        )


def upsert_traffic_estimate(domain_id: str, keyword: str, monthly_search_volume: int,
                            serp_rank: int | None, estimated_ctr: float,
                            estimated_monthly_visits: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO traffic_estimates
               (id, domain_id, keyword, monthly_search_volume, serp_rank,
                estimated_ctr, estimated_monthly_visits)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, keyword, monthly_search_volume,
             serp_rank, estimated_ctr, estimated_monthly_visits),
        )


def upsert_sitemap_metrics(domain_id: str, total_pages: int, last_modified) -> None:
    last_mod_str = last_modified.isoformat() if last_modified else None
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sitemap_metrics (id, domain_id, total_pages, last_modified)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, total_pages, last_mod_str),
        )


def upsert_site_change(domain_id: str, page_url: str, html_hash: str, has_changed: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO site_changes (id, domain_id, page_url, html_hash, has_changed)
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, page_url, html_hash, int(has_changed)),
        )


def get_last_dom_hash(domain_id: str, page_url: str) -> str | None:
    """Retrieve the most recent hash for a given page URL."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT html_hash FROM site_changes
               WHERE domain_id = ? AND page_url = ?
               ORDER BY checked_at DESC LIMIT 1""",
            (domain_id, page_url),
        ).fetchone()
    return row["html_hash"] if row else None


def log_scan_error(domain_id: str | None, module: str, error_type: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO scan_errors (id, domain_id, module, error_type, error_message)
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), domain_id, module, error_type, message),
        )
