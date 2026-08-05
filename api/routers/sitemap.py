"""
Sitemap router.
GET /api/domains/{id}/sitemap
"""

from fastapi import APIRouter, HTTPException
from db.sqlite import get_conn, rows_to_dicts

router = APIRouter(prefix="/api/domains", tags=["sitemap"])


@router.get("/{domain_id}/sitemap")
async def get_sitemap(domain_id: str):
    with get_conn() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT * FROM sitemap_metrics WHERE domain_id=?
               ORDER BY scanned_at DESC LIMIT 5""",
            (domain_id,),
        ).fetchall())

    if not rows:
        raise HTTPException(status_code=404, detail="No sitemap data found")

    latest = rows[0]
    page_growth_4w = latest["total_pages"] - rows[-1]["total_pages"] if len(rows) >= 2 else 0

    return {
        "domain_id": domain_id,
        "total_pages": latest["total_pages"],
        "page_growth_4w": page_growth_4w,
        "last_modified": latest.get("last_modified"),
        "scanned_at": latest["scanned_at"],
    }
