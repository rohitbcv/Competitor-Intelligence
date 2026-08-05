"""
Keywords router.
POST /api/keywords/upload  — upload keyword volume CSV
GET  /api/compare          — side-by-side comparison across domains
"""

import io
import csv
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from db.sqlite import get_conn, rows_to_dicts, row_to_dict

router = APIRouter(tags=["keywords"])


@router.post("/api/keywords/upload")
async def upload_keyword_csv(file: UploadFile = File(...)):
    """Upload a Google Ads Keyword Planner CSV (keyword, monthly_volume, competition)."""
    content = await file.read()
    text = content.decode("utf-8")

    inserted = updated = errors = 0
    reader = csv.DictReader(io.StringIO(text))

    with get_conn() as conn:
        for row in reader:
            try:
                keyword = row.get("keyword", "").strip().lower()
                volume = int(row.get("monthly_volume", 0))
                competition = row.get("competition", "MEDIUM").strip().upper()
                if not keyword or volume < 0:
                    errors += 1
                    continue

                existing = conn.execute(
                    "SELECT id FROM keyword_volumes WHERE keyword=?", (keyword,)
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE keyword_volumes SET monthly_volume=?, competition=?,
                           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                           WHERE keyword=?""",
                        (volume, competition, keyword),
                    )
                    updated += 1
                else:
                    import uuid
                    conn.execute(
                        """INSERT INTO keyword_volumes (id, keyword, monthly_volume, competition)
                           VALUES (?, ?, ?, ?)""",
                        (str(uuid.uuid4()), keyword, volume, competition),
                    )
                    inserted += 1
            except Exception:
                errors += 1

    return {"inserted": inserted, "updated": updated, "errors": errors}


@router.get("/api/compare")
async def compare_domains(domains: str = Query(..., description="Comma-separated domain UUIDs, max 5")):
    """Side-by-side comparison of up to 5 domains."""
    domain_ids = [d.strip() for d in domains.split(",")][:5]
    if not domain_ids:
        raise HTTPException(status_code=400, detail="At least one domain ID required")

    results = []
    with get_conn() as conn:
        for domain_id in domain_ids:
            domain = row_to_dict(conn.execute(
                "SELECT * FROM domains WHERE id=?", (domain_id,)
            ).fetchone())
            if not domain:
                continue

            traffic_rows = rows_to_dicts(conn.execute(
                """SELECT te.keyword, MAX(te.estimated_monthly_visits) AS estimated_monthly_visits
                   FROM traffic_estimates te
                   WHERE te.domain_id = ?
                   GROUP BY te.keyword""",
                (domain_id,),
            ).fetchall())
            total_visits = sum(r["estimated_monthly_visits"] for r in traffic_rows)

            tech_row = row_to_dict(conn.execute(
                """SELECT detected_tech FROM tech_profiles WHERE domain_id=?
                   ORDER BY scraped_at DESC LIMIT 1""",
                (domain_id,),
            ).fetchone())
            current_tech = tech_row.get("detected_tech", []) if tech_row else []

            results.append({
                "domain_id": domain_id,
                "domain": domain["domain_name"],
                "display_name": domain.get("display_name"),
                "total_estimated_monthly_visits": total_visits,
                "keywords_tracked": len(traffic_rows),
                "technologies": current_tech,
                "data_disclaimer": "estimate_7_11_pct_variance",
            })

    return results
