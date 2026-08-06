"""
Local SQLite Setup Script — creates the database and populates starter data.

Keyword discovery priority (highest → lowest):
  1. Google Ads KeywordPlanIdeaService (URL seed per domain) — real volumes, live ideas
  2. Hardcoded fallback seed list                            — zero volumes, bootstraps
     the keyword_volumes table so the app starts; volumes are filled on the
     first collector scan once the Google Ads API is configured.

Run once before starting the app:
    python3.10 setup_schema.py

The database is saved to:  data/tracker.db
"""

import logging
import uuid
from pathlib import Path
from db.sqlite import get_conn, init_db, DB_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ── Competitor domains ────────────────────────────────────────────────────────
# Each entry drives a URL-seed keyword discovery call to Google Ads.
# Add / remove domains here to change what the tracker monitors.
DOMAINS = [
    {"domain_name": "marriott.com", "display_name": "Marriott Hotels"},
    {"domain_name": "hilton.com",   "display_name": "Hilton Hotels"},
    {"domain_name": "hyatt.com",    "display_name": "Hyatt Hotels"},
    {"domain_name": "ihg.com",      "display_name": "IHG Hotels & Resorts"},
]

# ── Fallback seed keywords ────────────────────────────────────────────────────
# Used ONLY when the Google Ads API is not yet configured.
# monthly_volume = 0 intentionally — the collector's keyword_volume_fetcher
# will replace these with real Google data on the first scan after you
# configure google-ads.yaml.
#
# To add your own market/city, replace the terms below with queries relevant
# to the client's competitive set.
_FALLBACK_KEYWORDS = [
    # Generic hotel queries — market-level
    "hotels in new york city",
    "new york hotels",
    "best hotels in nyc",
    "hotels near times square",
    "manhattan hotels",
    "nyc hotel",
    "hotels in manhattan",
    "new york city hotels",
    "hotel in new york",
    "hotels nyc",
    # Location
    "hotels near central park nyc",
    "hotels near rockefeller center",
    "hotels near penn station nyc",
    "hotels near grand central station",
    "midtown manhattan hotels",
    "upper east side hotels nyc",
    "upper west side hotels nyc",
    "downtown manhattan hotels",
    "hotels near jfk airport",
    "hotels near laguardia airport",
    # Segment / class
    "luxury hotels new york",
    "5 star hotels nyc",
    "cheap hotels nyc",
    "budget hotels new york city",
    "boutique hotels new york",
    "family hotels new york city",
    # Transactional
    "hotel deals new york",
    "last minute hotels nyc",
    "hotel rooms new york",
    "book hotel new york",
    # Amenity long-tail
    "hotels with pool new york city",
    "hotels with rooftop bar nyc",
    "hotels with parking nyc",
    # Branded — Marriott portfolio
    "marriott new york",
    "marriott hotels nyc",
    "marriott times square",
    "marriott marquis nyc",
    "sheraton new york times square",
    "westin new york grand central",
    "w hotel new york",
    "courtyard marriott nyc",
    "marriott bonvoy new york hotels",
    # Branded — Hilton portfolio
    "hilton new york",
    "hilton hotels new york city",
    "waldorf astoria new york",
    "hampton inn new york city",
    "doubletree new york",
    # Branded — Hyatt portfolio
    "hyatt new york",
    "park hyatt new york",
    "grand hyatt nyc",
    "hyatt regency new york",
    # Branded — IHG portfolio
    "holiday inn new york",
    "intercontinental new york",
    "crowne plaza times square",
    "kimpton new york",
    # Comparison
    "marriott vs hilton new york",
    "hilton vs hyatt new york",
]


def _discover_or_fallback(domains: list[dict]) -> dict[str, int]:
    """
    Try to discover keywords for every domain via Google Ads URL seed.
    Returns { keyword: monthly_volume }.

    If the API is not configured, returns the fallback seed list with volume=0.
    Duplicate keywords across domains are de-duplicated (highest volume wins).
    """
    try:
        from collector.modules.keyword_volume_fetcher import (
            discover_keywords_for_domain,
            _is_configured,
        )
    except ImportError:
        logger.warning("keyword_volume_fetcher not importable — using fallback list.")
        return {kw: 0 for kw in _FALLBACK_KEYWORDS}

    if not _is_configured():
        logger.info(
            "Google Ads API not configured.\n"
            "  → Using %d fallback seed keywords (monthly_volume = 0).\n"
            "  → Configure google-ads.yaml and re-run setup_schema.py to get\n"
            "    live keyword ideas and real search volumes from Google.",
            len(_FALLBACK_KEYWORDS),
        )
        return {kw: 0 for kw in _FALLBACK_KEYWORDS}

    combined: dict[str, int] = {}
    for d in domains:
        logger.info("Discovering keywords for %s via Google Ads …", d["domain_name"])
        ideas = discover_keywords_for_domain(d["domain_name"])
        for kw, vol in ideas.items():
            # Keep the highest observed volume when the same keyword appears
            # for multiple domains (they share generic market queries).
            if kw not in combined or vol > combined[kw]:
                combined[kw] = vol

    if not combined:
        logger.warning("Google Ads returned no ideas — falling back to seed list.")
        return {kw: 0 for kw in _FALLBACK_KEYWORDS}

    logger.info("Google Ads discovery complete: %d unique keywords found.", len(combined))
    return combined


def main():
    print(f"\n{'='*56}")
    print("Competitor Intelligence Tracker — Local Setup")
    print(f"{'='*56}")
    print(f"Database: {DB_PATH}\n")

    init_db()
    print("✓ Tables initialised")

    # ── Keyword discovery ────────────────────────────────────────────────────
    print("\nStep 1/2 — Keyword discovery")
    keywords = _discover_or_fallback(DOMAINS)

    with get_conn() as conn:
        existing_kws = {
            r[0].lower()
            for r in conn.execute("SELECT keyword FROM keyword_volumes").fetchall()
        }
        inserted_kws = 0
        updated_kws = 0
        for kw, vol in keywords.items():
            if kw.lower() in existing_kws:
                if vol > 0:
                    conn.execute(
                        "UPDATE keyword_volumes SET monthly_volume = ? WHERE LOWER(keyword) = LOWER(?)",
                        (vol, kw),
                    )
                    updated_kws += 1
            else:
                conn.execute(
                    """INSERT INTO keyword_volumes (id, keyword, monthly_volume, competition)
                       VALUES (?, ?, ?, ?)""",
                    (str(uuid.uuid4()), kw, vol, _infer_competition(vol)),
                )
                inserted_kws += 1

    vol_note = "with real Google volumes" if any(v > 0 for v in keywords.values()) else "with volume=0 (API not configured)"
    print(
        f"  {len(existing_kws)} already present | "
        f"{inserted_kws} inserted | {updated_kws} updated — {vol_note}"
    )

    # ── Domain seeding ───────────────────────────────────────────────────────
    print("\nStep 2/2 — Domain seeding")
    with get_conn() as conn:
        existing_domains = {
            r[0] for r in conn.execute("SELECT domain_name FROM domains").fetchall()
        }
        inserted_domains = 0
        for d in DOMAINS:
            if d["domain_name"] not in existing_domains:
                conn.execute(
                    "INSERT INTO domains (id, domain_name, display_name) VALUES (?, ?, ?)",
                    (str(uuid.uuid4()), d["domain_name"], d["display_name"]),
                )
                inserted_domains += 1
    print(
        f"  {len(existing_domains)} already present | {inserted_domains} inserted"
    )

    print(f"\n{'='*56}")
    print("✅ Setup complete. Next steps:")
    if any(v == 0 for v in keywords.values()):
        print("   → Configure google-ads.yaml then re-run setup_schema.py")
        print("     to replace placeholder volumes with real Google data.")
    print("   1. Start API:  uvicorn api.main:app --reload --port 8000")
    print("   2. Start UI:   cd frontend && npm run dev")
    print(f"{'='*56}\n")


def _infer_competition(monthly_volume: int) -> str:
    """Infer competition tier from volume when the API doesn't provide it."""
    if monthly_volume == 0:
        return "UNKNOWN"
    if monthly_volume >= 10000:
        return "HIGH"
    if monthly_volume >= 3000:
        return "MEDIUM"
    return "LOW"


if __name__ == "__main__":
    main()
