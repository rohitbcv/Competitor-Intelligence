"""
Module: Keyword Discoverer

Automatically discovers relevant search keywords for any domain using:
  A. Sitemap URL parsing    → keyword candidates from real URL structure
  B. Google Autocomplete    → real queries people type for this brand
  C. Pattern generation     → brand + location + category combinations
  D. pytrends               → relative volume estimation vs anchor keyword
                              (falls back to a length-based heuristic on failure)

Called once when a new domain is added (no domain-specific keywords exist yet),
or on demand. Results are stored in domain_keyword_map + keyword_volumes tables.
"""

import re
import time
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# URL path segments that carry no keyword value
_IGNORE_SEGMENTS = {
    "www", "http", "https", "index", "home", "page", "en", "us", "gb", "au",
    "the", "and", "or", "of", "a", "an", "in", "at", "to", "for", "on",
    "with", "by", "contact", "about", "sitemap", "tag", "category",
    "search", "results", "terms", "privacy", "cookie", "careers", "press",
    "media", "news", "blog", "faq", "help", "support", "login", "account",
    "cart", "checkout", "wishlist", "profile", "register", "sign", "error",
    "static", "assets", "images", "img", "css", "js", "api", "admin",
}

_MIN_WORDS = 1
_MAX_WORDS = 6

# pytrends anchor: "hotels" ≈ 450,000 US monthly searches (well-established reference)
_ANCHOR_KW     = "hotels"
_ANCHOR_VOLUME = 450_000

# Known brand-name fixes for common domains
_BRAND_FIXES: dict[str, str] = {
    "fourseasons":      "four seasons",
    "ritzcarton":       "ritz carlton",
    "ritz-carlton":     "ritz carlton",
    "waldorfastoria":   "waldorf astoria",
    "ihg":              "ihg",
    "marriott":         "marriott",
    "hilton":           "hilton",
    "hyatt":            "hyatt",
    "fourpoints":       "four points",
    "stregis":          "st regis",
    "lemeridien":       "le meridien",
    "whotels":          "w hotels",
}


# ── Brand extraction ──────────────────────────────────────────────────────────

def get_brand_name(domain: str) -> str:
    """
    Extract a human-readable brand name from a domain.
    e.g. fourseasons.com → 'four seasons', marriott.com → 'marriott'
    """
    name = re.sub(r"\.(com|org|net|co|io|hotel|hotels|travel|biz).*$", "", domain.lower())
    name = re.sub(r"^www\.", "", name)
    name = re.sub(r"[-_]", " ", name).strip()
    clean = re.sub(r"\s+", "", name)
    return _BRAND_FIXES.get(clean, name).strip()


# ── Source A: Sitemap ─────────────────────────────────────────────────────────

def _extract_from_sitemap(domain: str) -> list[str]:
    """Parse sitemap and extract keyword candidates from URL path patterns."""
    from collector.modules.sitemap import parse_sitemap

    candidates: set[str] = set()
    try:
        sitemap_data = parse_sitemap(domain)
        urls: list[str] = sitemap_data.get("urls") or []

        for url in urls[:400]:
            try:
                path = urlparse(url if "://" in url else f"https://{url}").path.lower()

                # Skip non-content assets
                if any(path.endswith(ext) for ext in
                       [".jpg", ".jpeg", ".png", ".gif", ".css", ".js",
                        ".pdf", ".xml", ".ico", ".svg", ".webp"]):
                    continue
                if any(skip in path for skip in
                       ["/api/", "/admin/", "/wp-", "/assets/", "/_next/",
                        "/static/", "/__", "/cdn-cgi/"]):
                    continue

                # Split into slug-words
                raw_segs = [s for s in path.split("/") if s and len(s) > 2]
                segs: list[str] = []
                for seg in raw_segs:
                    word = re.sub(r"[-_]", " ", seg).strip()
                    word = re.sub(r"\d{4,}", "", word).strip()   # remove year-like numbers
                    word = re.sub(r"\s+", " ", word).strip()
                    if word and word not in _IGNORE_SEGMENTS and len(word) > 2:
                        segs.append(word)

                for seg in segs:
                    w = seg.split()
                    if _MIN_WORDS <= len(w) <= _MAX_WORDS:
                        candidates.add(seg)

                # Adjacent pairs
                for i in range(len(segs) - 1):
                    combo = f"{segs[i]} {segs[i + 1]}"
                    if len(combo.split()) <= _MAX_WORDS:
                        candidates.add(combo)

                # Triple
                if len(segs) >= 3:
                    combo = f"{segs[0]} {segs[1]} {segs[2]}"
                    if len(combo.split()) <= _MAX_WORDS:
                        candidates.add(combo)

            except Exception:
                continue

    except Exception as e:
        logger.warning("[KD] Sitemap extraction failed for %s: %s", domain, e)

    result = [k for k in candidates if _MIN_WORDS <= len(k.split()) <= _MAX_WORDS]
    logger.info("[KD][A] Sitemap yielded %d candidates", len(result))
    return result


# ── Source B: Google Autocomplete ─────────────────────────────────────────────

def _extract_from_autocomplete(brand: str) -> list[str]:
    """
    Scrape Google Autocomplete suggestions for brand-related queries.
    Uses the public suggest endpoint — no API key required.
    """
    suggestions: set[str] = set()
    seeds = [
        brand,
        f"{brand} hotel",
        f"{brand} hotels",
        f"{brand} resort",
        f"{brand} spa",
        f"{brand} booking",
        f"{brand} reservation",
        f"book {brand}",
        f"best {brand}",
        f"{brand} luxury",
        f"{brand} suite",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    for seed in seeds:
        try:
            resp = requests.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "q": seed, "hl": "en"},
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data[1]:
                    if isinstance(item, str):
                        kw = item.lower().strip()
                        if _MIN_WORDS <= len(kw.split()) <= _MAX_WORDS and len(kw) > 3:
                            suggestions.add(kw)
            time.sleep(0.4)
        except Exception as e:
            logger.debug("[KD] Autocomplete skip '%s': %s", seed, e)

    result = list(suggestions)
    logger.info("[KD][B] Autocomplete yielded %d candidates", len(result))
    return result


# ── Source C: Pattern generation ──────────────────────────────────────────────

_LOCATIONS = [
    "new york", "london", "paris", "dubai", "chicago", "los angeles",
    "miami", "las vegas", "singapore", "tokyo", "sydney", "hong kong",
    "san francisco", "boston", "seattle", "washington dc", "rome",
    "barcelona", "amsterdam", "bangkok",
]
_CATEGORIES = [
    "hotel", "hotels", "resort", "resorts", "spa", "suite", "suites",
    "rooms", "luxury hotel", "5 star hotel", "boutique hotel", "inn",
]
_ACTIONS = [
    "book", "reservation", "reservations", "booking", "deals", "rates",
    "check in", "availability",
]
_LOYALTY = ["rewards", "points", "membership", "loyalty", "status"]


def _generate_patterns(brand: str) -> list[str]:
    """Systematic brand + location / category / action keyword patterns."""
    patterns: set[str] = set()

    patterns.add(brand)

    for cat in _CATEGORIES:
        patterns.add(f"{brand} {cat}")

    for loc in _LOCATIONS[:10]:
        patterns.add(f"{brand} {loc}")
        patterns.add(f"{brand} hotel {loc}")

    for act in _ACTIONS:
        patterns.add(f"{brand} {act}")

    for loy in _LOYALTY:
        patterns.add(f"{brand} {loy}")

    result = [p for p in patterns if len(p.split()) <= _MAX_WORDS]
    logger.info("[KD][C] Pattern generation yielded %d candidates", len(result))
    return result


# ── Volume estimation ─────────────────────────────────────────────────────────

def _heuristic_volume(keyword: str, brand: str = "") -> int:
    """
    Fast volume estimate based on keyword length and type.
    Used as a fallback when pytrends is unavailable or rate-limited.

    Buckets are based on typical Keyword Planner distributions for hotel brands.
    """
    kw = keyword.lower().strip()
    words = kw.split()
    n = len(words)

    if kw == brand:
        return 18100        # brand alone → head term
    if brand and brand in kw and n <= 3:
        return 6600         # brand + 1-2 words → navigational
    if n <= 2 and any(t in kw for t in ["hotel", "hotels", "resort"]):
        return 9900         # generic hotel head term
    if n in (2, 3):
        return 3600         # mid-tail
    if n >= 4:
        return 1300         # long-tail
    return 2400


def _estimate_volumes_pytrends(keywords: list[str], brand: str) -> dict[str, int]:
    """
    Estimate monthly US search volumes via pytrends relative comparison.

    Method: compare each keyword against the anchor ("hotels" ≈ 450K/mo).
    Batches of 4 keywords (5th slot = anchor) to stay within pytrends limits.
    Falls back to _heuristic_volume() on any error.
    """
    if not keywords:
        return {}

    volumes: dict[str, int] = {}

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        batch_size = 4
        total_batches = (len(keywords) + batch_size - 1) // batch_size
        logger.info("[KD] Estimating volumes for %d keywords via pytrends (%d batches)…",
                    len(keywords), total_batches)

        for i in range(0, len(keywords), batch_size):
            batch = keywords[i: i + batch_size]
            payload = [_ANCHOR_KW] + batch

            try:
                time.sleep(6)   # mandatory pause between pytrends calls
                pytrends.build_payload(payload, timeframe="today 12-m", geo="US")
                df = pytrends.interest_over_time()

                if df is None or df.empty or _ANCHOR_KW not in df.columns:
                    for kw in batch:
                        volumes[kw] = _heuristic_volume(kw, brand)
                    continue

                ref_avg = float(df[_ANCHOR_KW].mean())
                if ref_avg == 0:
                    for kw in batch:
                        volumes[kw] = _heuristic_volume(kw, brand)
                    continue

                for kw in batch:
                    if kw in df.columns:
                        kw_avg = float(df[kw].mean())
                        estimated = int((kw_avg / ref_avg) * _ANCHOR_VOLUME)
                        volumes[kw] = max(100, min(estimated, 10_000_000))
                    else:
                        volumes[kw] = _heuristic_volume(kw, brand)

                logger.info("[KD] pytrends batch %d/%d done",
                            i // batch_size + 1, total_batches)

            except Exception as e:
                logger.warning("[KD] pytrends batch failed: %s — using heuristic", e)
                for kw in batch:
                    volumes[kw] = _heuristic_volume(kw, brand)

    except ImportError:
        logger.warning("[KD] pytrends not installed — using heuristic volumes")
        for kw in keywords:
            volumes[kw] = _heuristic_volume(kw, brand)
    except Exception as e:
        logger.warning("[KD] pytrends init error: %s — using heuristic", e)
        for kw in keywords:
            volumes[kw] = _heuristic_volume(kw, brand)

    return volumes


# ── Public entry point ────────────────────────────────────────────────────────

def discover_keywords(domain: str, max_keywords: int = 150) -> dict[str, int]:
    """
    Discover relevant keywords for a domain and estimate their US search volumes.

    Args:
        domain:       e.g. 'fourseasons.com'
        max_keywords: cap on total keywords returned (default 150)

    Returns:
        dict[keyword_string → estimated_monthly_volume]

    Pipeline:
      A. Sitemap URL parsing
      B. Google Autocomplete
      C. Brand pattern generation
      → deduplicate + clean
      → volume estimation via pytrends (fallback: heuristic)
    """
    brand = get_brand_name(domain)
    logger.info("[KD] ══ Starting keyword discovery for %s (brand: '%s') ══", domain, brand)

    all_candidates: set[str] = set()

    # A — Sitemap
    all_candidates.update(_extract_from_sitemap(domain))

    # B — Autocomplete
    all_candidates.update(_extract_from_autocomplete(brand))

    # C — Patterns
    all_candidates.update(_generate_patterns(brand))

    # ── Clean & filter ────────────────────────────────────────────────────────
    cleaned: set[str] = set()
    for kw in all_candidates:
        kw = re.sub(r"\s+", " ", kw.strip().lower())
        words = kw.split()
        if len(words) < _MIN_WORDS or len(words) > _MAX_WORDS:
            continue
        if len(kw) < 3:
            continue
        if all(w in _IGNORE_SEGMENTS for w in words):
            continue
        cleaned.add(kw)

    # Prioritize: autocomplete (most signal-rich) first, then patterns, then sitemap
    keyword_list = list(cleaned)[:max_keywords]

    logger.info("[KD] %d unique keywords after dedup/filter (cap: %d)",
                len(cleaned), max_keywords)

    # ── Volume estimation ─────────────────────────────────────────────────────
    volumes = _estimate_volumes_pytrends(keyword_list, brand)

    # Fill any gaps
    for kw in keyword_list:
        if kw not in volumes:
            volumes[kw] = _heuristic_volume(kw, brand)

    logger.info("[KD] ══ Discovery complete for %s: %d keywords ══", domain, len(volumes))
    return volumes
