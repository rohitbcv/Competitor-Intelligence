"""
Tech Stack router.
GET /api/domains/{id}/tech
GET /api/domains/{id}/tech/history
"""

from fastapi import APIRouter, HTTPException
from db.sqlite import get_conn, rows_to_dicts

router = APIRouter(prefix="/api/domains", tags=["tech"])


@router.get("/{domain_id}/tech")
async def get_tech(domain_id: str):
    with get_conn() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT * FROM tech_profiles WHERE domain_id=?
               ORDER BY scraped_at DESC LIMIT 1""",
            (domain_id,),
        ).fetchall())

    if not rows:
        raise HTTPException(status_code=404, detail="No tech data found for this domain")

    row = rows[0]
    return {
        "domain_id": domain_id,
        "technologies": row["detected_tech"],
        "scan_status": row["scan_status"],
        "scraped_at": row["scraped_at"],
    }


@router.get("/{domain_id}/tech/history")
async def get_tech_history(domain_id: str):
    with get_conn() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT * FROM tech_profiles WHERE domain_id=?
               ORDER BY scraped_at DESC LIMIT 20""",
            (domain_id,),
        ).fetchall())

    history = []
    for i, row in enumerate(rows):
        current_tech = row["detected_tech"] or []
        prev_tech = rows[i + 1]["detected_tech"] if i + 1 < len(rows) else []
        added = [t for t in current_tech if t not in prev_tech]
        removed = [t for t in prev_tech if t not in current_tech]
        history.append({
            "scraped_at": row["scraped_at"],
            "technologies": current_tech,
            "scan_status": row["scan_status"],
            "added": added,
            "removed": removed,
        })

    return history
