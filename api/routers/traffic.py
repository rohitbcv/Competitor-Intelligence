"""
Traffic router.
GET /api/domains/{id}/traffic
GET /api/domains/{id}/traffic/trend
"""

from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, HTTPException
from db.sqlite import get_conn, rows_to_dicts, row_to_dict

router = APIRouter(prefix="/api/domains", tags=["traffic"])


@router.get("/{domain_id}/traffic")
async def get_traffic(domain_id: str):
    with get_conn() as conn:
        domain = row_to_dict(conn.execute(
            "SELECT domain_name, display_name FROM domains WHERE id=?", (domain_id,)
        ).fetchone())
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        # For each keyword: get the two most recent rows that have visits > 0.
        # Row 1 = current period, Row 2 = previous period (for delta).
        # Rows with 0 visits (SERP-blocked scans) are excluded from delta logic.
        all_rows = rows_to_dicts(conn.execute(
            """SELECT keyword, monthly_search_volume, serp_rank,
                      estimated_ctr, estimated_monthly_visits, estimated_at
               FROM traffic_estimates
               WHERE domain_id = ?
               ORDER BY keyword, estimated_at DESC""",
            (domain_id,),
        ).fetchall())

    # Group by keyword keeping only non-zero rows, ordered newest → oldest
    nonzero: dict[str, list[dict]] = {}
    for r in all_rows:
        kw = r["keyword"]
        if r["estimated_monthly_visits"] > 0:
            nonzero.setdefault(kw, []).append(r)

    keyword_breakdown = []
    # Also keep zero-visit keywords so unranked ones still appear in the table
    seen_kw: set[str] = set()
    for r in all_rows:
        kw = r["keyword"]
        if kw in seen_kw:
            continue
        seen_kw.add(kw)

        periods = nonzero.get(kw, [])
        if periods:
            current = periods[0]["estimated_monthly_visits"]
            prev    = periods[1]["estimated_monthly_visits"] if len(periods) > 1 else current
            row     = periods[0]
        else:
            current = prev = 0
            row = r

        delta_visits = current - prev
        delta_pct = round((delta_visits / prev * 100), 1) if prev else 0.0

        keyword_breakdown.append({
            "keyword": kw,
            "monthly_volume": row["monthly_search_volume"],
            "serp_rank": row["serp_rank"],
            "ctr": float(row["estimated_ctr"] or 0),
            "estimated_visits": current,
            "delta_visits": delta_visits,
            "delta_pct": delta_pct,
        })

    total_visits = sum(k["estimated_visits"] for k in keyword_breakdown)

    return {
        "domain": domain["domain_name"],
        "domain_id": domain_id,
        "total_estimated_monthly_visits": total_visits,
        "keywords_tracked": len(keyword_breakdown),
        "keyword_breakdown": sorted(keyword_breakdown, key=lambda x: x["estimated_visits"], reverse=True),
        "accuracy": "estimate_7_11_pct_variance",
        "data_disclaimer": (
            "All traffic figures are estimates with ±7–11% variance. "
            "They do not represent actual analytics."
        ),
    }


@router.get("/{domain_id}/traffic/trend")
async def get_traffic_trend(domain_id: str):
    with get_conn() as conn:
        rows = rows_to_dicts(conn.execute(
            """SELECT estimated_monthly_visits, estimated_at FROM traffic_estimates
               WHERE domain_id=? ORDER BY estimated_at DESC""",
            (domain_id,),
        ).fetchall())

    weekly: dict = defaultdict(int)
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["estimated_at"].replace("Z", "+00:00"))
            week_key = dt.strftime("%Y-W%W")
        except Exception:
            week_key = (row["estimated_at"] or "unknown")[:10]
        weekly[week_key] += row["estimated_monthly_visits"]

    return [{"week": k, "est_traffic": v} for k, v in sorted(weekly.items(), reverse=True)]
