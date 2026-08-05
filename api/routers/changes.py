"""
DOM Changes router.
GET /api/domains/{id}/changes
"""

from fastapi import APIRouter, HTTPException
from db.sqlite import get_conn, rows_to_dicts

router = APIRouter(prefix="/api/domains", tags=["changes"])


@router.get("/{domain_id}/changes")
async def get_changes(domain_id: str):
    with get_conn() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT * FROM site_changes WHERE domain_id=?
               ORDER BY checked_at DESC LIMIT 50""",
            (domain_id,),
        ).fetchall())

    return {
        "domain_id": domain_id,
        "total_monitored_pages": len(set(r["page_url"] for r in rows)),
        "changed_count": sum(1 for r in rows if r.get("has_changed")),
        "events": [
            {
                "page_url": r["page_url"],
                "has_changed": bool(r.get("has_changed")),
                "html_hash": r["html_hash"],
                "checked_at": r["checked_at"],
            }
            for r in rows
        ],
    }
