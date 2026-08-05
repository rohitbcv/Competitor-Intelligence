"""
Local SQLite Setup Script — creates the database and seeds starter data.

Run once before starting the app for the first time:
    python3.10 setup_schema.py

The database is saved to:  data/tracker.db
"""

import json
import uuid
import hashlib
from pathlib import Path
from db.sqlite import get_conn, init_db, DB_PATH

SAMPLE_KEYWORDS = [
    # Broad / head
    {"keyword": "hotels in new york city", "monthly_volume": 74000, "competition": "HIGH"},
    {"keyword": "new york hotels", "monthly_volume": 110000, "competition": "HIGH"},
    {"keyword": "best hotels in nyc", "monthly_volume": 22200, "competition": "HIGH"},
    {"keyword": "hotels near times square", "monthly_volume": 40500, "competition": "HIGH"},
    {"keyword": "manhattan hotels", "monthly_volume": 33100, "competition": "HIGH"},
    {"keyword": "nyc hotel", "monthly_volume": 27100, "competition": "HIGH"},
    {"keyword": "hotels in manhattan", "monthly_volume": 49500, "competition": "HIGH"},
    {"keyword": "new york city hotels", "monthly_volume": 60500, "competition": "HIGH"},
    {"keyword": "hotel in new york", "monthly_volume": 33100, "competition": "HIGH"},
    {"keyword": "hotels nyc", "monthly_volume": 45400, "competition": "HIGH"},
    # Location-specific
    {"keyword": "hotels near central park nyc", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "hotels near rockefeller center", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "hotels near penn station nyc", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "hotels near grand central station", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "midtown manhattan hotels", "monthly_volume": 22200, "competition": "HIGH"},
    {"keyword": "upper east side hotels nyc", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "upper west side hotels nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "downtown manhattan hotels", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "hotels near 5th avenue nyc", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "hotels near empire state building", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "hotels near nyc airport", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "hotels near jfk airport", "monthly_volume": 12100, "competition": "HIGH"},
    {"keyword": "hotels near laguardia airport", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "hotels near union square nyc", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "hotels in brooklyn nyc", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "hotels near broadway nyc", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "hotels near madison square garden", "monthly_volume": 12100, "competition": "HIGH"},
    {"keyword": "chelsea hotels nyc", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "tribeca hotels nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "soho hotels new york", "monthly_volume": 6600, "competition": "MEDIUM"},
    # Segment / class
    {"keyword": "luxury hotels new york", "monthly_volume": 18100, "competition": "HIGH"},
    {"keyword": "5 star hotels nyc", "monthly_volume": 12100, "competition": "HIGH"},
    {"keyword": "4 star hotels nyc", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "cheap hotels nyc", "monthly_volume": 27100, "competition": "HIGH"},
    {"keyword": "budget hotels new york city", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "affordable hotels nyc", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "boutique hotels new york", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "family hotels new york city", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "pet friendly hotels nyc", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "romantic hotels nyc", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "business hotels new york", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "extended stay hotels nyc", "monthly_volume": 5400, "competition": "MEDIUM"},
    # Transactional
    {"keyword": "hotel deals new york", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "cheap hotels nyc tonight", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "last minute hotels nyc", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "hotel rooms new york", "monthly_volume": 14800, "competition": "HIGH"},
    {"keyword": "book hotel new york", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "new york hotel reservations", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "nyc hotel deals this weekend", "monthly_volume": 3600, "competition": "HIGH"},
    {"keyword": "hotels new york cheap rates", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "discount hotels new york city", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "hotel packages new york", "monthly_volume": 4400, "competition": "MEDIUM"},
    # Amenity long-tail
    {"keyword": "hotels with pool new york city", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "hotels with gym nyc", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "hotels with spa nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "hotels with rooftop bar nyc", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "hotels with kitchenette nyc", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "hotels with free breakfast nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "hotels with parking nyc", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "hotels with city view nyc", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "all inclusive hotels nyc", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "hotels with balcony nyc", "monthly_volume": 2400, "competition": "LOW"},
    # Informational
    {"keyword": "best luxury hotels new york 2025", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "best midtown hotels nyc", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "top rated hotels new york city", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "best hotels near times square", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "best value hotels nyc", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "most popular hotels in nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "new york hotel reviews", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "new york hotel comparison", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "hotels worth it nyc", "monthly_volume": 1900, "competition": "LOW"},
    # Marriott branded
    {"keyword": "marriott new york", "monthly_volume": 18100, "competition": "HIGH"},
    {"keyword": "marriott times square", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "marriott hotels nyc", "monthly_volume": 12100, "competition": "HIGH"},
    {"keyword": "marriott marquis nyc", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "marriott midtown new york", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "marriott downtown nyc", "monthly_volume": 3600, "competition": "HIGH"},
    {"keyword": "marriott bonvoy new york hotels", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "marriott broadway new york", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "ny marriott east side", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "marriott hotel new york city reservations", "monthly_volume": 2400, "competition": "HIGH"},
    {"keyword": "marriott points redemption nyc", "monthly_volume": 1600, "competition": "MEDIUM"},
    {"keyword": "westin new york grand central", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "sheraton new york times square", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "w hotel new york", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "courtyard marriott nyc", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "marriott rewards new york", "monthly_volume": 2400, "competition": "MEDIUM"},
    # Hilton branded
    {"keyword": "hilton new york", "monthly_volume": 14800, "competition": "HIGH"},
    {"keyword": "hilton midtown nyc", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "hilton hotels new york city", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "hilton times square", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "hilton hotel manhattan", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "hilton new york midtown", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "waldorf astoria new york", "monthly_volume": 12100, "competition": "HIGH"},
    {"keyword": "doubletree new york", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "hampton inn new york city", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "hilton garden inn nyc", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "hilton honors nyc hotels", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "curio collection new york", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "embassy suites new york city", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "hilton downtown manhattan", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "hilton points nyc redemption", "monthly_volume": 1600, "competition": "LOW"},
    # Hyatt branded
    {"keyword": "hyatt new york", "monthly_volume": 9900, "competition": "HIGH"},
    {"keyword": "park hyatt new york", "monthly_volume": 5400, "competition": "MEDIUM"},
    {"keyword": "grand hyatt nyc", "monthly_volume": 6600, "competition": "MEDIUM"},
    {"keyword": "hyatt times square nyc", "monthly_volume": 3600, "competition": "HIGH"},
    {"keyword": "hyatt midtown manhattan", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "hyatt place new york", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "andaz 5th avenue new york", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "thompson central park new york", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "alila manhattan hotel", "monthly_volume": 1600, "competition": "LOW"},
    {"keyword": "world of hyatt new york", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "hyatt regency new york", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "hyatt centric times square", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "hyatt grand central new york", "monthly_volume": 2900, "competition": "MEDIUM"},
    # IHG branded
    {"keyword": "holiday inn new york", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "holiday inn times square", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "intercontinental new york", "monthly_volume": 6600, "competition": "HIGH"},
    {"keyword": "intercontinental times square", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "kimpton new york", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "kimpton hotel manhattan", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "crowne plaza times square", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "crowne plaza new york", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "staybridge suites times square", "monthly_volume": 1900, "competition": "MEDIUM"},
    {"keyword": "candlewood suites new york", "monthly_volume": 1300, "competition": "LOW"},
    {"keyword": "hotel indigo lower east side", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "voco times square south", "monthly_volume": 1600, "competition": "LOW"},
    {"keyword": "ihg rewards new york hotels", "monthly_volume": 1900, "competition": "MEDIUM"},
    # Events & occasions
    {"keyword": "hotels nyc new years eve", "monthly_volume": 8100, "competition": "HIGH"},
    {"keyword": "hotels near javits center nyc", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "hotels near yankee stadium", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "hotels near msg new york", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "wedding hotels new york city", "monthly_volume": 4400, "competition": "MEDIUM"},
    {"keyword": "honeymoon hotels nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "hotels with meeting rooms nyc", "monthly_volume": 2900, "competition": "MEDIUM"},
    {"keyword": "conference hotels new york city", "monthly_volume": 3600, "competition": "MEDIUM"},
    # Seasonal
    {"keyword": "hotels nyc christmas", "monthly_volume": 5400, "competition": "HIGH"},
    {"keyword": "hotels nyc thanksgiving", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "spring break hotels nyc", "monthly_volume": 3600, "competition": "MEDIUM"},
    {"keyword": "summer hotels deals nyc", "monthly_volume": 4400, "competition": "HIGH"},
    {"keyword": "hotels nyc labor day weekend", "monthly_volume": 2900, "competition": "HIGH"},
    # Comparison
    {"keyword": "marriott vs hilton new york", "monthly_volume": 1900, "competition": "LOW"},
    {"keyword": "direct booking hotel nyc", "monthly_volume": 2400, "competition": "MEDIUM"},
    {"keyword": "book direct marriott new york", "monthly_volume": 1600, "competition": "MEDIUM"},
    {"keyword": "marriott best rate guarantee nyc", "monthly_volume": 1300, "competition": "LOW"},
    {"keyword": "hilton vs hyatt new york", "monthly_volume": 1300, "competition": "LOW"},
]

SAMPLE_DOMAINS = [
    {"domain_name": "marriott.com", "display_name": "Marriott Hotels"},
    {"domain_name": "hilton.com",   "display_name": "Hilton Hotels"},
    {"domain_name": "hyatt.com",    "display_name": "Hyatt Hotels"},
    {"domain_name": "ihg.com",      "display_name": "IHG Hotels & Resorts"},
]


def main():
    print(f"\n{'='*52}")
    print("Competitor Intelligence Tracker — Local Setup")
    print(f"{'='*52}")
    print(f"Database: {DB_PATH}\n")

    # Create tables
    init_db()
    print("✓ Tables initialised")

    with get_conn() as conn:
        # Seed keywords
        existing_kws = {r[0] for r in conn.execute(
            "SELECT keyword FROM keyword_volumes"
        ).fetchall()}
        to_insert = [k for k in SAMPLE_KEYWORDS if k["keyword"] not in existing_kws]
        for kw in to_insert:
            conn.execute(
                """INSERT INTO keyword_volumes (id, keyword, monthly_volume, competition)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid.uuid4()), kw["keyword"], kw["monthly_volume"], kw["competition"]),
            )
        print(f"✓ Keywords: {len(existing_kws)} already present, {len(to_insert)} inserted")

        # Seed domains
        existing_domains = {r[0] for r in conn.execute(
            "SELECT domain_name FROM domains"
        ).fetchall()}
        inserted = 0
        for d in SAMPLE_DOMAINS:
            if d["domain_name"] not in existing_domains:
                conn.execute(
                    """INSERT INTO domains (id, domain_name, display_name)
                       VALUES (?, ?, ?)""",
                    (str(uuid.uuid4()), d["domain_name"], d["display_name"]),
                )
                inserted += 1
        print(f"✓ Domains:  {len(existing_domains)} already present, {inserted} inserted")

    print("\n✅ Setup complete. Next steps:")
    print("   1. Run seed:     python3.10 seed_test_data.py")
    print("   2. Start API:    python3.10 -m uvicorn api.main:app --port 8000")
    print("   3. Start UI:     cd frontend && npm run dev\n")


if __name__ == "__main__":
    main()
