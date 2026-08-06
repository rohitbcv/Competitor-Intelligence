"""
Seed realistic SERP rank + traffic estimate data into the local SQLite database.

Run: python3.10 seed_test_data.py
"""

import hashlib
import json
import uuid
from db.sqlite import get_conn, init_db

# ── 2026 CTR curves + intent model (mirrors traffic_estimator.py exactly) ────
# Source: Visionary Marketing (21.7M impressions, 2026), navboost meta-analysis.
BRANDED_CTR = {1:0.564,2:0.224,3:0.127,4:0.084,5:0.078,
               6:0.042,7:0.033,8:0.026,9:0.019,10:0.012}
GENERIC_CTR = {1:0.248,2:0.114,3:0.062,4:0.038,5:0.026,
               6:0.018,7:0.013,8:0.009,9:0.007,10:0.005}
for p in range(11,21): BRANDED_CTR[p]=0.005; GENERIC_CTR[p]=0.002

# AI Overview discount by intent (source: Ahrefs 2025/2026, Seer Interactive)
AIO_DISCOUNT = {
    "branded":       0.95,
    "transactional": 0.82,
    "commercial":    0.68,
    "informational": 0.42,
    "generic":       0.72,
}

BRAND_TOKENS = {
    "marriott.com": ["marriott","westin","sheraton","w hotel","courtyard"],
    "hilton.com":   ["hilton","hampton inn","doubletree","waldorf","curio","embassy suites"],
    "hyatt.com":    ["hyatt","park hyatt","grand hyatt","andaz","alila","thompson"],
    "ihg.com":      ["holiday inn","intercontinental","kimpton","crowne plaza",
                      "staybridge","candlewood","hotel indigo","voco"],
}

_TRANSACTIONAL = ["book","reserv","tonight","last minute","deal","discount",
                   "cheap rate","package","availability","check in","booking"]
_COMMERCIAL    = ["best","top ","vs ","compare","comparison","review","worth","popular","ranked"]
_INFORMATIONAL = ["what is","how to","how do","why ","guide","tips","near me"]

def is_branded(keyword, domain):
    return any(t in keyword.lower() for t in BRAND_TOKENS.get(domain, []))

def classify_intent(keyword, domain):
    if is_branded(keyword, domain): return "branded"
    kw = keyword.lower()
    if any(s in kw for s in _TRANSACTIONAL): return "transactional"
    if any(s in kw for s in _COMMERCIAL):    return "commercial"
    if any(s in kw for s in _INFORMATIONAL): return "informational"
    return "generic"

def ctr(rank, keyword, domain):
    if rank is None: return 0.0
    intent = classify_intent(keyword, domain)
    base   = (BRANDED_CTR if intent=="branded" else GENERIC_CTR).get(rank, 0.0)
    return round(base * AIO_DISCOUNT[intent], 5)

# ── Per-domain SERP ranks ─────────────────────────────────────────────────────
def _build_ranks():
    ranks = {
        # Broad / head
        "hotels in new york city":      {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "new york hotels":              {"marriott.com":8,"hilton.com":9,"hyatt.com":10},
        "best hotels in nyc":           {"marriott.com":6,"hilton.com":7,"hyatt.com":8},
        "hotels near times square":     {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "manhattan hotels":             {"marriott.com":6,"hilton.com":7,"hyatt.com":9},
        "nyc hotel":                    {"marriott.com":8,"hilton.com":9,"hyatt.com":10},
        "hotels in manhattan":          {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "new york city hotels":         {"marriott.com":7,"hilton.com":8,"hyatt.com":10},
        "hotel in new york":            {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "hotels nyc":                   {"marriott.com":8,"hilton.com":9,"hyatt.com":10},
        # Location
        "hotels near central park nyc": {"marriott.com":7,"hilton.com":6,"hyatt.com":5},
        "hotels near rockefeller center":{"marriott.com":5,"hilton.com":6,"hyatt.com":8},
        "hotels near penn station nyc": {"marriott.com":6,"hilton.com":5,"hyatt.com":None},
        "hotels near grand central station":{"marriott.com":5,"hilton.com":4,"hyatt.com":6},
        "midtown manhattan hotels":     {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "upper east side hotels nyc":   {"marriott.com":8,"hilton.com":7,"hyatt.com":5},
        "upper west side hotels nyc":   {"marriott.com":None,"hilton.com":8,"hyatt.com":6},
        "downtown manhattan hotels":    {"marriott.com":7,"hilton.com":None,"hyatt.com":9},
        "hotels near 5th avenue nyc":   {"marriott.com":6,"hilton.com":7,"hyatt.com":5},
        "hotels near empire state building":{"marriott.com":7,"hilton.com":6,"hyatt.com":None},
        "hotels near nyc airport":      {"marriott.com":8,"hilton.com":7,"hyatt.com":None},
        "hotels near jfk airport":      {"marriott.com":7,"hilton.com":6,"hyatt.com":None},
        "hotels near laguardia airport":{"marriott.com":6,"hilton.com":5,"hyatt.com":None},
        "hotels near union square nyc": {"marriott.com":None,"hilton.com":None,"hyatt.com":7},
        "hotels in brooklyn nyc":       {"marriott.com":9,"hilton.com":8,"hyatt.com":None},
        "hotels near broadway nyc":     {"marriott.com":5,"hilton.com":6,"hyatt.com":8},
        "hotels near madison square garden":{"marriott.com":4,"hilton.com":5,"hyatt.com":7},
        "chelsea hotels nyc":           {"marriott.com":None,"hilton.com":8,"hyatt.com":None},
        "tribeca hotels nyc":           {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "soho hotels new york":         {"marriott.com":9,"hilton.com":None,"hyatt.com":8},
        # Segment
        "luxury hotels new york":       {"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "5 star hotels nyc":            {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "4 star hotels nyc":            {"marriott.com":6,"hilton.com":5,"hyatt.com":7},
        "cheap hotels nyc":             {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "budget hotels new york city":  {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "affordable hotels nyc":        {"marriott.com":10,"hilton.com":9,"hyatt.com":None},
        "boutique hotels new york":     {"marriott.com":8,"hilton.com":None,"hyatt.com":7},
        "family hotels new york city":  {"marriott.com":6,"hilton.com":5,"hyatt.com":8},
        "pet friendly hotels nyc":      {"marriott.com":7,"hilton.com":8,"hyatt.com":None},
        "romantic hotels nyc":          {"marriott.com":7,"hilton.com":None,"hyatt.com":5},
        "business hotels new york":     {"marriott.com":5,"hilton.com":4,"hyatt.com":6},
        "extended stay hotels nyc":     {"marriott.com":6,"hilton.com":7,"hyatt.com":None},
        # Transactional
        "hotel deals new york":         {"marriott.com":9,"hilton.com":10,"hyatt.com":None},
        "cheap hotels nyc tonight":     {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "last minute hotels nyc":       {"marriott.com":10,"hilton.com":None,"hyatt.com":None},
        "hotel rooms new york":         {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "book hotel new york":          {"marriott.com":8,"hilton.com":9,"hyatt.com":10},
        "new york hotel reservations":  {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "nyc hotel deals this weekend": {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "hotels new york cheap rates":  {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "discount hotels new york city":{"marriott.com":10,"hilton.com":None,"hyatt.com":None},
        "hotel packages new york":      {"marriott.com":6,"hilton.com":7,"hyatt.com":8},
        # Amenity
        "hotels with pool new york city":{"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "hotels with gym nyc":          {"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "hotels with spa nyc":          {"marriott.com":5,"hilton.com":6,"hyatt.com":4},
        "hotels with rooftop bar nyc":  {"marriott.com":7,"hilton.com":8,"hyatt.com":6},
        "hotels with kitchenette nyc":  {"marriott.com":6,"hilton.com":7,"hyatt.com":None},
        "hotels with free breakfast nyc":{"marriott.com":7,"hilton.com":6,"hyatt.com":8},
        "hotels with parking nyc":      {"marriott.com":6,"hilton.com":5,"hyatt.com":7},
        "hotels with city view nyc":    {"marriott.com":5,"hilton.com":6,"hyatt.com":4},
        "all inclusive hotels nyc":     {"marriott.com":None,"hilton.com":None,"hyatt.com":None},
        "hotels with balcony nyc":      {"marriott.com":7,"hilton.com":8,"hyatt.com":6},
        # Informational
        "best luxury hotels new york 2025":{"marriott.com":6,"hilton.com":7,"hyatt.com":8},
        "best midtown hotels nyc":      {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "top rated hotels new york city":{"marriott.com":6,"hilton.com":5,"hyatt.com":7},
        "best hotels near times square":{"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "best value hotels nyc":        {"marriott.com":7,"hilton.com":6,"hyatt.com":8},
        "most popular hotels in nyc":   {"marriott.com":6,"hilton.com":5,"hyatt.com":7},
        "new york hotel reviews":       {"marriott.com":8,"hilton.com":7,"hyatt.com":9},
        "new york hotel comparison":    {"marriott.com":7,"hilton.com":8,"hyatt.com":9},
        "hotels worth it nyc":          {"marriott.com":None,"hilton.com":9,"hyatt.com":None},
        # Marriott branded — own brand #1, others None
        "marriott new york":            {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott times square":        {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott hotels nyc":          {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott marquis nyc":         {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott midtown new york":    {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott downtown nyc":        {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott bonvoy new york hotels":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott broadway new york":   {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "ny marriott east side":        {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott hotel new york city reservations":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott points redemption nyc":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "westin new york grand central":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "sheraton new york times square":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "w hotel new york":             {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "courtyard marriott nyc":       {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott rewards new york":    {"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        # Hilton branded
        "hilton new york":              {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton midtown nyc":           {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton hotels new york city":  {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton times square":          {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton hotel manhattan":       {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton new york midtown":      {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "waldorf astoria new york":     {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "doubletree new york":          {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hampton inn new york city":    {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton garden inn nyc":        {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton honors nyc hotels":     {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "curio collection new york":    {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "embassy suites new york city": {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton downtown manhattan":    {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        "hilton points nyc redemption": {"marriott.com":None,"hilton.com":1,"hyatt.com":None},
        # Hyatt branded
        "hyatt new york":               {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "park hyatt new york":          {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "grand hyatt nyc":              {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt times square nyc":       {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt midtown manhattan":      {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt place new york":         {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "andaz 5th avenue new york":    {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "thompson central park new york":{"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "alila manhattan hotel":        {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "world of hyatt new york":      {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt regency new york":       {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt centric times square":   {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        "hyatt grand central new york": {"marriott.com":None,"hilton.com":None,"hyatt.com":1},
        # IHG branded
        "holiday inn new york":         {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "holiday inn times square":     {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "intercontinental new york":    {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "intercontinental times square":{"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "kimpton new york":             {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "kimpton hotel manhattan":      {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "crowne plaza times square":    {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "crowne plaza new york":        {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "staybridge suites times square":{"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "candlewood suites new york":   {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "hotel indigo lower east side": {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "voco times square south":      {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        "ihg rewards new york hotels":  {"marriott.com":None,"hilton.com":None,"hyatt.com":None,"ihg.com":1},
        # Events & seasonal
        "hotels nyc new years eve":     {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "hotels near javits center nyc":{"marriott.com":6,"hilton.com":5,"hyatt.com":None},
        "hotels near yankee stadium":   {"marriott.com":8,"hilton.com":None,"hyatt.com":None},
        "hotels near msg new york":     {"marriott.com":5,"hilton.com":6,"hyatt.com":8},
        "wedding hotels new york city": {"marriott.com":5,"hilton.com":6,"hyatt.com":7},
        "honeymoon hotels nyc":         {"marriott.com":7,"hilton.com":None,"hyatt.com":6},
        "hotels with meeting rooms nyc":{"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "conference hotels new york city":{"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "hotels nyc christmas":         {"marriott.com":6,"hilton.com":7,"hyatt.com":8},
        "hotels nyc thanksgiving":      {"marriott.com":6,"hilton.com":7,"hyatt.com":8},
        "spring break hotels nyc":      {"marriott.com":7,"hilton.com":8,"hyatt.com":None},
        "summer hotels deals nyc":      {"marriott.com":8,"hilton.com":9,"hyatt.com":None},
        "hotels nyc labor day weekend": {"marriott.com":7,"hilton.com":8,"hyatt.com":None},
        # Comparison
        "marriott vs hilton new york":  {"marriott.com":2,"hilton.com":3,"hyatt.com":None},
        "direct booking hotel nyc":     {"marriott.com":4,"hilton.com":5,"hyatt.com":6},
        "book direct marriott new york":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "marriott best rate guarantee nyc":{"marriott.com":1,"hilton.com":None,"hyatt.com":None},
        "hilton vs hyatt new york":     {"marriott.com":None,"hilton.com":2,"hyatt.com":3},
    }

    # Backfill IHG ranks for generic (non-competitor-branded) keywords
    for keyword, domain_ranks in ranks.items():
        if "ihg.com" in domain_ranks:
            continue
        if any(is_branded(keyword, d) for d in ["marriott.com","hilton.com","hyatt.com"]):
            domain_ranks["ihg.com"] = None
            continue
        hilton_rank = domain_ranks.get("hilton.com")
        domain_ranks["ihg.com"] = (hilton_rank + 1) if hilton_rank else None

    return ranks


DOMAINS_INFO = {
    "marriott.com": {"display": "Marriott Hotels", "pages": 8420},
    "hilton.com":   {"display": "Hilton Hotels",   "pages": 6180},
    "hyatt.com":    {"display": "Hyatt Hotels",    "pages": 4350},
    "ihg.com":      {"display": "IHG Hotels & Resorts", "pages": 7150},
}


def _seed_snapshot(conn, domain_name: str, domain_id: str,
                   ranks: dict, volumes: dict,
                   timestamp: str, prev_multipliers: dict | None = None) -> tuple[int, int]:
    """
    Insert one full snapshot of keyword_rankings + traffic_estimates for a domain.

    prev_multipliers: optional {keyword: float} — if provided, multiplies the
    computed visits by that factor to simulate last week's slightly lower traffic.
    Ranks stay the same so CTR curves don't swing wildly.

    Returns (ranked_count, total_visits).
    """
    total_visits = 0
    ranked = 0
    for keyword, domain_ranks in ranks.items():
        rank = domain_ranks.get(domain_name)
        vol = volumes.get(keyword, 0)
        c = ctr(rank, keyword, domain_name)
        long_tail = 0.80 if vol < 200 else 1.0
        visits = int(vol * c * long_tail)
        if prev_multipliers and keyword in prev_multipliers:
            visits = int(visits * prev_multipliers[keyword])
        total_visits += visits
        if rank:
            ranked += 1

        conn.execute(
            "INSERT INTO keyword_rankings (id,domain_id,keyword,rank_position) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), domain_id, keyword, rank),
        )
        conn.execute(
            """INSERT INTO traffic_estimates
               (id,domain_id,keyword,monthly_search_volume,serp_rank,
                estimated_ctr,estimated_monthly_visits,estimated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), domain_id, keyword, vol, rank, c, visits, timestamp),
        )
    return ranked, total_visits


def main():
    init_db()

    ranks = _build_ranks()

    import random
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    ts_current  = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_previous = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Per-keyword multiplier for the previous week: 0.85–0.92 of current visits.
    # This simulates realistic +8–18% weekly traffic growth without rank changes,
    # avoiding the extreme CTR swings that occur when rank shifts by just 1 position.
    ranks_for_mult = _build_ranks()
    all_keywords = list(ranks_for_mult.keys())
    random.seed(42)   # fixed seed → reproducible deltas
    prev_multipliers = {kw: round(random.uniform(0.85, 0.92), 4) for kw in all_keywords}

    with get_conn() as conn:
        volumes = {r[0]: r[1] for r in conn.execute(
            "SELECT keyword, monthly_volume FROM keyword_volumes"
        ).fetchall()}
        domain_rows = {r[0]: r[1] for r in conn.execute(
            "SELECT domain_name, id FROM domains WHERE is_active=1"
        ).fetchall()}

    print(f"\n{'='*56}")
    print(f"Seeding {len(ranks)} keywords × {len(domain_rows)} domains (2 snapshots)")
    print(f"{'='*56}")

    totals = {}
    with get_conn() as conn:
        for domain_name, domain_id in domain_rows.items():
            info = DOMAINS_INFO.get(domain_name)
            if not info:
                continue

            # Clear old data
            for table in ["traffic_estimates", "keyword_rankings",
                           "sitemap_metrics", "site_changes"]:
                conn.execute(f"DELETE FROM {table} WHERE domain_id=?", (domain_id,))

            # Sitemap
            conn.execute(
                "INSERT INTO sitemap_metrics (id,domain_id,total_pages,last_modified) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), domain_id, info["pages"], "2026-07-20T00:00:00Z"),
            )

            # DOM baseline
            conn.execute(
                "INSERT INTO site_changes (id,domain_id,page_url,html_hash,has_changed) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), domain_id, f"https://{domain_name}",
                 hashlib.md5(f"{domain_name}-2026-07".encode()).hexdigest(), 0),
            )

            # Previous week snapshot — same ranks, 85–92% of current visits
            _seed_snapshot(conn, domain_name, domain_id, ranks, volumes,
                           timestamp=ts_previous, prev_multipliers=prev_multipliers)

            # Current week snapshot — full visits
            ranked, total_visits = _seed_snapshot(conn, domain_name, domain_id,
                                                   ranks, volumes,
                                                   timestamp=ts_current)

            totals[domain_name] = total_visits
            print(f"\n  {info['display']}  ({domain_name})")
            print(f"    ✓ Sitemap:   {info['pages']:,} pages")
            print(f"    ✓ SERP:      {ranked}/{len(ranks)} keywords ranked (current week)")
            print(f"    ✓ Traffic:   ~{total_visits:,} visits/month (est., current week)")

    print(f"\n{'='*56}")
    print("Estimated monthly organic visits (current week)")
    print(f"{'='*56}")
    for dn, t in totals.items():
        print(f"  {DOMAINS_INFO[dn]['display']:24s}  ~{t:>8,} visits/month")
    print(f"\n✅ Done! Data saved to: data/tracker.db\n")


if __name__ == "__main__":
    main()
