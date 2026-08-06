"""Module C: SERP Rank Checker — googlesearch-python with mandatory rate limiting."""

import time
import random
import logging
from datetime import datetime, timezone
from googlesearch import search

logger = logging.getLogger(__name__)

MAX_RESULTS = 100
MAX_KEYWORDS_PER_CYCLE = 200

# Between-query pause (seconds). Randomised to mimic human browsing cadence.
# Lower bound 10s prevents Google's per-minute threshold (≈6 req/min).
# Upper bound 20s adds jitter so timing patterns are not machine-regular.
INTER_QUERY_DELAY = (10, 20)

# IP-block probe: two short attempts before declaring the IP unusable.
# Total probe time ≤ 30s so local runs fail fast.
PROBE_DELAYS = [10, 20]

# Normal backoffs after a 429 / CAPTCHA on a non-probe keyword.
# Escalating: 20s → 45s → 90s, then mark as blocked.
BACKOFF_DELAYS = [20, 45, 90]

# After this many consecutive failures, declare the IP blocked.
MAX_CONSECUTIVE_FAILURES = 3


def _search_with_backoff(query: str, delays: list[int], num: int = MAX_RESULTS) -> list[str]:
    """Run a Google search with backoff on 429/CAPTCHA. Returns [] if all attempts fail."""
    for attempt, delay in enumerate(delays):
        try:
            urls = list(search(query, num_results=num, sleep_interval=0))
            return urls
        except Exception as exc:
            error_str = str(exc).lower()
            if "429" in error_str or "captcha" in error_str or "rate" in error_str:
                logger.warning(
                    "SERP rate limit hit for '%s' (attempt %d/%d). Waiting %ds.",
                    query, attempt + 1, len(delays), delay
                )
                time.sleep(delay)
            else:
                raise
    return []


def check_serp_ranks(domain: str, keywords: list[str]) -> list[dict]:
    """
    Check SERP rank for each keyword for a given domain.

    Returns list of: {"keyword": str, "rank_position": int | None}

    IP-block detection: probes with the first keyword using short delays.
    If Google rejects it, all keywords are skipped immediately (≤20s total).
    This prevents scans from hanging when run from a rate-limited local IP.

    Note: SERP works reliably from GitHub Actions (fresh IP per run).
    """
    if not keywords:
        return []

    keywords = keywords[:MAX_KEYWORDS_PER_CYCLE]
    results = []
    start_time = time.time()

    # ── IP-block probe: try first keyword with short delays ─────────────────
    probe_kw = keywords[0]
    probe_urls = _search_with_backoff(probe_kw, delays=PROBE_DELAYS)

    if not probe_urls:
        # Google is blocking this IP — skip everything immediately
        elapsed = time.time() - start_time
        logger.warning(
            "SERP IP blocked after %.0fs probe (all %d attempts failed for '%s'). "
            "Skipping all %d keywords. For reliable SERP data, run from GitHub Actions.",
            elapsed, len(PROBE_DELAYS), probe_kw, len(keywords)
        )
        return [{"keyword": kw, "rank_position": None, "skipped": "ip_blocked"} for kw in keywords]

    # First keyword succeeded — record its result
    rank = next(
        (idx for idx, url in enumerate(probe_urls, 1) if domain.lower() in url.lower()),
        None
    )
    results.append({"keyword": probe_kw, "rank_position": rank})
    consecutive_failures = 0

    # Delay before next query
    time.sleep(random.uniform(*INTER_QUERY_DELAY))

    # ── Process remaining keywords ───────────────────────────────────────────
    for keyword in keywords[1:]:
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "%d consecutive SERP failures for %s — IP now blocked. Skipping %d remaining keywords.",
                consecutive_failures, domain, len(keywords) - len(results)
            )
            for remaining in keywords[len(results):]:
                results.append({"keyword": remaining, "rank_position": None, "skipped": "blocked"})
            break

        try:
            urls = _search_with_backoff(keyword, delays=BACKOFF_DELAYS)
            if not urls:
                results.append({"keyword": keyword, "rank_position": None, "skipped": "blocked"})
                consecutive_failures += 1
            else:
                rank = next(
                    (idx for idx, url in enumerate(urls, 1) if domain.lower() in url.lower()),
                    None
                )
                results.append({"keyword": keyword, "rank_position": rank})
                consecutive_failures = 0

        except Exception as exc:
            logger.error("SERP error for keyword '%s': %s", keyword, exc)
            results.append({"keyword": keyword, "rank_position": None, "error": str(exc)})
            consecutive_failures += 1

        time.sleep(random.uniform(*INTER_QUERY_DELAY))

    total_elapsed = time.time() - start_time
    found = sum(1 for r in results if r.get("rank_position") is not None)
    logger.info(
        "SERP complete for %s: %d/%d keywords ranked, %.0fs elapsed",
        domain, found, len(results), total_elapsed
    )
    return results
