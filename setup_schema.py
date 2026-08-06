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
# Volumes are research-backed estimates (Google Keyword Planner ranges, 2026).
# Once google-ads.yaml is configured, re-run setup_schema.py and these will
# be replaced with real 12-month averages from Google's own data.
#
# Format: (keyword, monthly_volume, competition)
_FALLBACK_KEYWORDS: list[tuple[str, int, str]] = [
    # Generic hotel queries — market-level
    ("hotels in new york city",        74000, "HIGH"),
    ("new york hotels",               110000, "HIGH"),
    ("best hotels in nyc",             22200, "HIGH"),
    ("hotels near times square",       40500, "HIGH"),
    ("manhattan hotels",               33100, "HIGH"),
    ("nyc hotel",                      27100, "HIGH"),
    ("hotels in manhattan",            49500, "HIGH"),
    ("new york city hotels",           60500, "HIGH"),
    ("hotel in new york",              33100, "HIGH"),
    ("hotels nyc",                     45400, "HIGH"),
    # Location
    ("hotels near central park nyc",    8100, "HIGH"),
    ("hotels near rockefeller center",  6600, "HIGH"),
    ("hotels near penn station nyc",    9900, "HIGH"),
    ("hotels near grand central station", 8100, "HIGH"),
    ("midtown manhattan hotels",       22200, "HIGH"),
    ("upper east side hotels nyc",      4400, "MEDIUM"),
    ("upper west side hotels nyc",      3600, "MEDIUM"),
    ("downtown manhattan hotels",       9900, "HIGH"),
    ("hotels near jfk airport",        12100, "HIGH"),
    ("hotels near laguardia airport",   8100, "HIGH"),
    # Segment / class
    ("luxury hotels new york",         18100, "HIGH"),
    ("5 star hotels nyc",              12100, "HIGH"),
    ("cheap hotels nyc",               27100, "HIGH"),
    ("budget hotels new york city",     9900, "HIGH"),
    ("boutique hotels new york",        9900, "HIGH"),
    ("family hotels new york city",     8100, "HIGH"),
    # Transactional
    ("hotel deals new york",            8100, "HIGH"),
    ("last minute hotels nyc",          6600, "HIGH"),
    ("hotel rooms new york",           14800, "HIGH"),
    ("book hotel new york",             9900, "HIGH"),
    # Amenity long-tail
    ("hotels with pool new york city",  4400, "MEDIUM"),
    ("hotels with rooftop bar nyc",     5400, "MEDIUM"),
    ("hotels with parking nyc",         6600, "MEDIUM"),
    # Branded — Marriott portfolio
    ("marriott new york",              18100, "HIGH"),
    ("marriott hotels nyc",            12100, "HIGH"),
    ("marriott times square",           9900, "HIGH"),
    ("marriott marquis nyc",            8100, "HIGH"),
    ("sheraton new york times square",  6600, "HIGH"),
    ("westin new york grand central",   4400, "MEDIUM"),
    ("w hotel new york",                5400, "HIGH"),
    ("courtyard marriott nyc",          4400, "MEDIUM"),
    ("marriott bonvoy new york hotels", 4400, "HIGH"),
    # Branded — Hilton portfolio
    ("hilton new york",                14800, "HIGH"),
    ("hilton hotels new york city",     8100, "HIGH"),
    ("waldorf astoria new york",       12100, "HIGH"),
    ("hampton inn new york city",       9900, "HIGH"),
    ("doubletree new york",             6600, "MEDIUM"),
    # Branded — Hyatt portfolio
    ("hyatt new york",                  9900, "HIGH"),
    ("park hyatt new york",             5400, "MEDIUM"),
    ("grand hyatt nyc",                 6600, "MEDIUM"),
    ("hyatt regency new york",          4400, "MEDIUM"),
    # Branded — IHG portfolio
    ("holiday inn new york",            8100, "HIGH"),
    ("intercontinental new york",       6600, "HIGH"),
    ("crowne plaza times square",       4400, "HIGH"),
    ("kimpton new york",                3600, "MEDIUM"),
    # Comparison
    ("marriott vs hilton new york",     1900, "LOW"),
    ("hilton vs hyatt new york",        1300, "LOW"),
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
            "  → Using %d fallback seed keywords with estimated volumes.\n"
            "  → Configure google-ads.yaml and re-run setup_schema.py to get\n"
            "    live keyword ideas and real search volumes from Google.",
            len(_FALLBACK_KEYWORDS),
        )
        return {kw: vol for kw, vol, _ in _FALLBACK_KEYWORDS}

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
        return {kw: vol for kw, vol, _ in _FALLBACK_KEYWORDS}

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

    # Build a lookup for known competition tiers from the fallback list
    _fallback_competition = {kw.lower(): comp for kw, _, comp in _FALLBACK_KEYWORDS}

    with get_conn() as conn:
        existing_kws = {
            r[0].lower()
            for r in conn.execute("SELECT keyword FROM keyword_volumes").fetchall()
        }
        inserted_kws = 0
        updated_kws = 0
        for kw, vol in keywords.items():
            competition = _fallback_competition.get(kw.lower(), _infer_competition(vol))
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
                    (str(uuid.uuid4()), kw, vol, competition),
                )
                inserted_kws += 1

    vol_note = "with real Google volumes" if not any(v == 0 for v in keywords.values()) else "with estimated fallback volumes"
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
