"""Module C: SERP Rank Checker.

Primary:  DuckDuckGo Search via `ddgs` library (free, no API key, no quota).
Fallback: googlesearch-python (when ddgs is unavailable).

DuckDuckGo returns real organic web rankings and is not subject to IP blocks
or API quotas, making it reliable both locally and on GitHub Actions.
"""

import time
import random
import logging

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False

try:
    from googlesearch import search as _gs_search_fn
    _GS_AVAILABLE = True
except ImportError:
    _GS_AVAILABLE = False

logger = logging.getLogger(__name__)

MAX_RESULTS = 30           # Top-30 positions checked per keyword
MAX_KEYWORDS_PER_CYCLE = 200
MAX_CONSECUTIVE_FAILURES = 3

# Polite delay between queries (DuckDuckGo doesn't require it but it's good practice)
QUERY_DELAY = (1.5, 3.0)


# ── DuckDuckGo (primary) ─────────────────────────────────────────────────────

def _ddg_search(query: str) -> list[str]:
    """Search DuckDuckGo and return result URLs (top MAX_RESULTS)."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS))
        return [r.get("href", "") for r in results if r.get("href")]
    except Exception as exc:
        logger.warning("DDG search error for '%s': %s", query, exc)
        return []


def _check_ranks_ddg(domain: str, keywords: list[str]) -> list[dict]:
    logger.info("[C] DuckDuckGo SERP: %s — checking %d keywords", domain, len(keywords))
    results = []
    consecutive_failures = 0

    for i, keyword in enumerate(keywords):
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("[C] DDG: %d consecutive failures — skipping %d remaining.",
                           consecutive_failures, len(keywords) - len(results))
            for kw in keywords[len(results):]:
                results.append({"keyword": kw, "rank_position": None, "skipped": "blocked"})
            break

        urls = _ddg_search(keyword)

        if not urls:
            consecutive_failures += 1
            results.append({"keyword": keyword, "rank_position": None, "skipped": "no_results"})
        else:
            consecutive_failures = 0
            rank = next(
                (idx for idx, url in enumerate(urls, 1) if domain.lower() in url.lower()),
                None,
            )
            results.append({"keyword": keyword, "rank_position": rank})

        if i < len(keywords) - 1:
            time.sleep(random.uniform(*QUERY_DELAY))

    found = sum(1 for r in results if r.get("rank_position") is not None)
    logger.info("[C] DDG complete for %s: %d/%d ranked", domain, found, len(results))
    return results


# ── googlesearch-python (fallback) ───────────────────────────────────────────

def _check_ranks_fallback(domain: str, keywords: list[str]) -> list[dict]:
    logger.info("[C] googlesearch fallback: %s — checking %d keywords", domain, len(keywords))
    results = []
    consecutive_failures = 0

    for i, keyword in enumerate(keywords):
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            for kw in keywords[len(results):]:
                results.append({"keyword": kw, "rank_position": None, "skipped": "blocked"})
            break

        try:
            urls = list(_gs_search_fn(keyword, num_results=MAX_RESULTS, sleep_interval=0))
            if not urls:
                consecutive_failures += 1
                results.append({"keyword": keyword, "rank_position": None, "skipped": "no_results"})
            else:
                consecutive_failures = 0
                rank = next(
                    (idx for idx, url in enumerate(urls, 1) if domain.lower() in url.lower()),
                    None,
                )
                results.append({"keyword": keyword, "rank_position": rank})
        except Exception as exc:
            logger.error("[C] googlesearch error '%s': %s", keyword, exc)
            results.append({"keyword": keyword, "rank_position": None, "error": str(exc)})
            consecutive_failures += 1

        if i < len(keywords) - 1:
            time.sleep(random.uniform(2, 5))

    found = sum(1 for r in results if r.get("rank_position") is not None)
    logger.info("[C] Fallback complete for %s: %d/%d ranked", domain, found, len(results))
    return results


# ── Public API ───────────────────────────────────────────────────────────────

def check_serp_ranks(domain: str, keywords: list[str]) -> list[dict]:
    """
    Check SERP rank for each keyword for *domain*.

    Returns list of: {"keyword": str, "rank_position": int | None}

    Uses DuckDuckGo (free, no quota, no IP blocks) as primary.
    Falls back to googlesearch-python if ddgs is unavailable.
    """
    if not keywords:
        return []

    keywords = keywords[:MAX_KEYWORDS_PER_CYCLE]

    if _DDGS_AVAILABLE:
        return _check_ranks_ddg(domain, keywords)
    elif _GS_AVAILABLE:
        logger.warning("[C] ddgs not available — using googlesearch-python fallback")
        return _check_ranks_fallback(domain, keywords)
    else:
        logger.error("[C] No SERP library available. Install ddgs: pip install ddgs")
        return [{"keyword": kw, "rank_position": None, "skipped": "no_library"}
                for kw in keywords]
