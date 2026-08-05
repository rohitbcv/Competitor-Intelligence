"""
Domains router — CRUD for tracked competitor domains.
GET /api/domains, POST /api/domains, DELETE /api/domains/{id}
GET /api/domains/{id}/overview
"""

import uuid
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query
from api.models.schemas import DomainCreate, DomainResponse, OverviewResponse
from db.sqlite import get_conn, rows_to_dicts, row_to_dict

router = APIRouter(prefix="/api/domains", tags=["domains"])


def _normalize_domain(raw: str) -> str:
    """
    Extract the bare hostname from any user input — full URL or plain domain.

    Examples:
      https://www.margaritavilleresorts.com/margaritaville-beach-resort-south-padre-island
        → margaritavilleresorts.com
      www.marriott.com/hotels/travel  → marriott.com
      Marriott.com                    → marriott.com
    """
    raw = raw.strip().lower()
    if not raw:
        return raw
    # urlparse needs a scheme to parse correctly
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path   # netloc is empty if no scheme was present
    # Strip www. prefix for consistency
    if host.startswith("www."):
        host = host[4:]
    return host.strip("/")


@router.get("", response_model=list[DomainResponse])
async def list_domains(client_id: str | None = Query(None)):
    with get_conn() as conn:
        if client_id:
            rows = conn.execute(
                "SELECT * FROM domains WHERE is_active=1 AND client_id=?", (client_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM domains WHERE is_active=1"
            ).fetchall()
    return rows_to_dicts(rows)


@router.post("", response_model=DomainResponse, status_code=201)
async def add_domain(payload: DomainCreate):
    # Normalize: accept full URLs or bare domains, strip www. and paths
    domain_name = _normalize_domain(payload.domain_name)
    if not domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name")

    # Auto display_name: title-case the domain root if caller didn't provide one
    display_name = payload.display_name
    if not display_name:
        root = domain_name.split(".")[0]   # "margaritavilleresorts" from "margaritavilleresorts.com"
        display_name = root.replace("-", " ").title()

    domain_id = str(uuid.uuid4())
    with get_conn() as conn:
        # Prevent duplicates silently — return existing row if domain already tracked
        existing = conn.execute(
            "SELECT * FROM domains WHERE domain_name=? AND is_active=1", (domain_name,)
        ).fetchone()
        if existing:
            return row_to_dict(existing)

        conn.execute(
            """INSERT INTO domains (id, domain_name, display_name, client_id)
               VALUES (?, ?, ?, ?)""",
            (domain_id, domain_name, display_name, payload.client_id),
        )
        row = conn.execute(
            "SELECT * FROM domains WHERE id=?", (domain_id,)
        ).fetchone()
    return row_to_dict(row)


@router.delete("/{domain_id}", status_code=204)
async def remove_domain(domain_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE domains SET is_active=0 WHERE id=?", (domain_id,)
        )


@router.get("/{domain_id}/overview", response_model=OverviewResponse)
async def get_overview(domain_id: str):
    with get_conn() as conn:
        domain = row_to_dict(conn.execute(
            "SELECT * FROM domains WHERE id=?", (domain_id,)
        ).fetchone())
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        # Traffic — best (highest-visit) estimate per keyword across all scans.
        # Using MAX avoids zero-visit rows from SERP-blocked scans overriding good seeded data.
        traffic_rows = rows_to_dicts(conn.execute(
            """SELECT te.*
               FROM traffic_estimates te
               INNER JOIN (
                   SELECT keyword, MAX(estimated_monthly_visits) AS best_visits
                   FROM traffic_estimates
                   WHERE domain_id = ?
                   GROUP BY keyword
               ) best ON best.keyword = te.keyword
                       AND best.best_visits = te.estimated_monthly_visits
               WHERE te.domain_id = ?
               GROUP BY te.keyword""",
            (domain_id, domain_id),
        ).fetchall())

        total_visits = sum(r["estimated_monthly_visits"] for r in traffic_rows)
        top_keywords = sorted(
            traffic_rows, key=lambda x: x["estimated_monthly_visits"], reverse=True
        )[:5]

        # Tech
        tech_rows = rows_to_dicts(conn.execute(
            """SELECT * FROM tech_profiles WHERE domain_id=?
               ORDER BY scraped_at DESC LIMIT 2""",
            (domain_id,),
        ).fetchall())
        current_tech = tech_rows[0]["detected_tech"] if tech_rows else []
        prev_tech = tech_rows[1]["detected_tech"] if len(tech_rows) > 1 else []
        added = [t for t in current_tech if t not in prev_tech]
        removed = [t for t in prev_tech if t not in current_tech]

        # Sitemap
        sitemap_row = row_to_dict(conn.execute(
            """SELECT * FROM sitemap_metrics WHERE domain_id=?
               ORDER BY scanned_at DESC LIMIT 1""",
            (domain_id,),
        ).fetchone())

        # DOM changes
        changes_rows = rows_to_dicts(conn.execute(
            """SELECT * FROM site_changes WHERE domain_id=?
               ORDER BY checked_at DESC LIMIT 20""",
            (domain_id,),
        ).fetchall())

    changed_pages = sum(1 for r in changes_rows if r.get("has_changed"))
    last_change = changes_rows[0]["checked_at"] if changes_rows else None
    last_scan = traffic_rows[0]["estimated_at"] if traffic_rows else None

    return {
        "domain": domain["domain_name"],
        "display_name": domain.get("display_name"),
        "traffic": {
            "total_estimated_monthly_visits": total_visits,
            "keywords_tracked": len(traffic_rows),
            "top_keywords": top_keywords,
            "accuracy": "estimate_7_11_pct_variance",
        },
        "tech_stack": {
            "current": current_tech,
            "changes_since_last_scan": {
                "added": [f"added: {t}" for t in added],
                "removed": [f"removed: {t}" for t in removed],
            },
        },
        "sitemap": {
            "total_pages": sitemap_row.get("total_pages", 0),
            "last_modified": sitemap_row.get("last_modified"),
        },
        "dom_changes": {
            "changed_pages": changed_pages,
            "monitored_pages": len(set(r["page_url"] for r in changes_rows)),
            "last_change": last_change,
        },
        "last_scan": last_scan,
        "data_disclaimer": (
            "All traffic figures are estimates with ±7–11% variance. "
            "They do not represent actual analytics."
        ),
    }
