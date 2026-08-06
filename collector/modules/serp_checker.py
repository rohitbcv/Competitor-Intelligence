"""Module C: SERP Rank Checker.

Primary:  Google Custom Search JSON API (reliable, official).
Fallback: googlesearch-python (works locally when CSE creds are absent).

Free CSE quota: 100 queries/day.  We cap keywords at MAX_KEYWORDS_CSE per
domain when running via CSE so the daily budget is never blown in one run.
"""

import os
import time
import random
import logging
import requests
from googlesearch import search

logger = logging.getLogger(__name__)

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# CSE: 1 request = top-10 results.  30 keywords × 3 domains = 90 req/day < 100 limit.
MAX_KEYWORDS_CSE = 30
MAX_KEYWORDS_FALLBACK = 200

# Fallback (googlesearch-python) probe delays
PROBE_DELAYS = [5, 10]
BACKOFF_DELAYS = [5, 15, 30]
MAX_CONSECUTIVE_FAILURES = 2


# ── Credentials ─────────────────────────────────────────────────────────────

def _cse_configured() -> tuple[str, str] | tuple[None, None]:
    """Return (api_key, cse_id) if both are set, else (None, None)."""
    api_key = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    cse_id  = os.getenv("GOOGLE_CSE_ID", "").strip()
    if api_key and cse_id:
        return api_key, cse_id
    return None, None


# ── Google CSE ───────────────────────────────────────────────────────────────

def _cse_search(query: str, api_key: str, cse_id: str) -> list[str]:
    """One CSE request → up to 10 result URLs (top-10 SERP)."""
    params = {
        "key": api_key,
        "cx":  cse_id,
        "q":   query,
        "num": 10,
    }
    try:
        resp = requests.get(CSE_ENDPOINT, params=params, timeout=15)
        if resp.status_code == 429:
            logger.warning("CSE daily quota exceeded for query '%s'.", query)
            return []
        if resp.status_code == 403:
            logger.warning("CSE 403 Forbidden for query '%s' — check API key/quota.", query)
            return []
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [item.get("link", "") for item in items]
    except requests.RequestException as exc:
        logger.error("CSE request error for '%s': %s", query, exc)
        return []


def _check_ranks_cse(domain: str, keywords: list[str],
                     api_key: str, cse_id: str) -> list[dict]:
    keywords = keywords[:MAX_KEYWORDS_CSE]
    logger.info("[C] CSE SERP: %s — checking top %d keywords", domain, len(keywords))

    results = []
    consecutive_failures = 0

    for i, keyword in enumerate(keywords):
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("CSE: %d consecutive failures — quota likely exhausted. "
                           "Skipping %d remaining keywords.",
                           consecutive_failures, len(keywords) - len(results))
            for kw in keywords[len(results):]:
                results.append({"keyword": kw, "rank_position": None, "skipped": "quota_exceeded"})
            break

        urls = _cse_search(keyword, api_key, cse_id)

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

        # Stay well within the 100 req/day free limit
        if i < len(keywords) - 1:
            time.sleep(random.uniform(1.0, 2.0))

    found = sum(1 for r in results if r.get("rank_position") is not None)
    logger.info("[C] CSE complete for %s: %d/%d ranked", domain, found, len(results))
    return results


# ── googlesearch-python fallback ─────────────────────────────────────────────

def _gs_search(query: str, delays: list[int]) -> list[str]:
    for attempt, delay in enumerate(delays):
        try:
            return list(search(query, num_results=100, sleep_interval=0))
        except Exception as exc:
            err = str(exc).lower()
            if "429" in err or "captcha" in err or "rate" in err:
                logger.warning("Fallback SERP rate-limit '%s' attempt %d/%d — waiting %ds.",
                               query, attempt + 1, len(delays), delay)
                time.sleep(delay)
            else:
                raise
    return []


def _check_ranks_fallback(domain: str, keywords: list[str]) -> list[dict]:
    keywords = keywords[:MAX_KEYWORDS_FALLBACK]
    logger.info("[C] Fallback SERP: %s — checking %d keywords", domain, len(keywords))

    results = []
    start = time.time()

    # IP-block probe
    probe_urls = _gs_search(keywords[0], PROBE_DELAYS)
    if not probe_urls:
        elapsed = time.time() - start
        logger.warning("SERP IP blocked after %.0fs probe ('%s'). "
                       "Skipping all %d keywords. Run from GitHub Actions for reliable data.",
                       elapsed, keywords[0], len(keywords))
        return [{"keyword": kw, "rank_position": None, "skipped": "ip_blocked"}
                for kw in keywords]

    rank = next(
        (i for i, url in enumerate(probe_urls, 1) if domain.lower() in url.lower()), None
    )
    results.append({"keyword": keywords[0], "rank_position": rank})
    consecutive_failures = 0
    time.sleep(random.uniform(2, 5))

    for keyword in keywords[1:]:
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("Fallback SERP: %d consecutive failures for %s — skipping rest.",
                           consecutive_failures, domain)
            for kw in keywords[len(results):]:
                results.append({"keyword": kw, "rank_position": None, "skipped": "blocked"})
            break

        try:
            urls = _gs_search(keyword, BACKOFF_DELAYS)
            if not urls:
                results.append({"keyword": keyword, "rank_position": None, "skipped": "blocked"})
                consecutive_failures += 1
            else:
                rank = next(
                    (i for i, url in enumerate(urls, 1) if domain.lower() in url.lower()), None
                )
                results.append({"keyword": keyword, "rank_position": rank})
                consecutive_failures = 0
        except Exception as exc:
            logger.error("Fallback SERP error '%s': %s", keyword, exc)
            results.append({"keyword": keyword, "rank_position": None, "error": str(exc)})
            consecutive_failures += 1

        time.sleep(random.uniform(2, 5))

    found = sum(1 for r in results if r.get("rank_position") is not None)
    logger.info("[C] Fallback SERP complete for %s: %d/%d ranked", domain, found, len(results))
    return results


# ── Public API ───────────────────────────────────────────────────────────────

def check_serp_ranks(domain: str, keywords: list[str]) -> list[dict]:
    """
    Check SERP rank for each keyword for *domain*.

    Returns list of: {"keyword": str, "rank_position": int | None}

    Uses Google CSE API when GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID are set,
    otherwise falls back to googlesearch-python (works locally, may be blocked).
    """
    if not keywords:
        return []

    api_key, cse_id = _cse_configured()
    if api_key and cse_id:
        return _check_ranks_cse(domain, keywords, api_key, cse_id)
    return _check_ranks_fallback(domain, keywords)
