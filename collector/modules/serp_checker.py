"""Module C: SERP Rank Checker — Google with DuckDuckGo fallback.

Strategy:
  1. Probe Google with the first keyword (short delays).
  2. If Google responds → use Google for all keywords.
  3. If Google blocks (429/empty) → fall back to DuckDuckGo (ddgs library).
     DuckDuckGo is less aggressively rate-limited and requires no API key.
     Rankings are very close to Google for branded/navigational queries.
"""

import time
import random
import logging
from datetime import datetime, timezone
from googlesearch import search as google_search

logger = logging.getLogger(__name__)

MAX_RESULTS = 100
MAX_KEYWORDS_PER_CYCLE = 200

# Short backoffs for the IP-block probe
PROBE_DELAYS = [5, 10]

# Normal backoffs once we know Google is responding
BACKOFF_DELAYS = [5, 15, 30]

MAX_CONSECUTIVE_FAILURES = 2


# ── Google helpers ──────────────────────────────────────────────────────────

def _google_search_with_backoff(query: str, delays: list[int], num: int = MAX_RESULTS) -> list[str]:
    """Run a Google search with backoff on 429/CAPTCHA. Returns [] if all attempts fail."""
    for attempt, delay in enumerate(delays):
        try:
            urls = list(google_search(query, num_results=num, sleep_interval=0))
            return urls
        except Exception as exc:
            error_str = str(exc).lower()
            if "429" in error_str or "captcha" in error_str or "rate" in error_str:
                logger.warning(
                    "Google rate limit on '%s' (attempt %d/%d). Waiting %ds.",
                    query, attempt + 1, len(delays), delay,
                )
                time.sleep(delay)
            else:
                raise
    return []


# ── DuckDuckGo helpers ──────────────────────────────────────────────────────

def _ddg_search(query: str, num: int = MAX_RESULTS) -> list[str]:
    """Search DuckDuckGo and return a list of result URLs (up to num)."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num))
        return [r.get("href", "") for r in results if r.get("href")]
    except Exception as exc:
        logger.warning("DDG search failed for '%s': %s", query, exc)
        return []


def _check_domain_in_urls(domain: str, urls: list[str]) -> int | None:
    """Return 1-based rank of first URL containing domain, or None."""
    domain_lower = domain.lower()
    return next(
        (idx for idx, url in enumerate(urls, 1) if domain_lower in url.lower()),
        None,
    )


# ── Main entry point ────────────────────────────────────────────────────────

def check_serp_ranks(domain: str, keywords: list[str]) -> list[dict]:
    """
    Check SERP rank for each keyword for a given domain.

    Returns list of: {"keyword": str, "rank_position": int | None, "source": "google"|"ddg"}

    Flow:
      - Probe Google with the first keyword.
      - If Google works → use Google for all (with 2-5s delays).
      - If Google blocks → switch to DuckDuckGo for all keywords.
    """
    if not keywords:
        return []

    keywords = keywords[:MAX_KEYWORDS_PER_CYCLE]
    results = []
    start_time = time.time()

    # ── Step 1: Probe Google ────────────────────────────────────────────────
    probe_kw = keywords[0]
    probe_urls = _google_search_with_backoff(probe_kw, delays=PROBE_DELAYS)

    if probe_urls:
        logger.info("Google is accessible for %s. Using Google SERP.", domain)
        source = "google"

        rank = _check_domain_in_urls(domain, probe_urls)
        results.append({"keyword": probe_kw, "rank_position": rank, "source": source})
        consecutive_failures = 0
        time.sleep(random.uniform(2, 5))

        for keyword in keywords[1:]:
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "%d consecutive failures for %s — switching remaining to DDG.",
                    consecutive_failures, domain,
                )
                # Fall back to DDG for remaining keywords
                for remaining in keywords[len(results):]:
                    urls = _ddg_search(remaining)
                    rank = _check_domain_in_urls(domain, urls) if urls else None
                    results.append({"keyword": remaining, "rank_position": rank, "source": "ddg"})
                    time.sleep(random.uniform(1, 2))
                break

            try:
                urls = _google_search_with_backoff(keyword, delays=BACKOFF_DELAYS)
                if not urls:
                    results.append({"keyword": keyword, "rank_position": None, "skipped": "blocked", "source": source})
                    consecutive_failures += 1
                else:
                    rank = _check_domain_in_urls(domain, urls)
                    results.append({"keyword": keyword, "rank_position": rank, "source": source})
                    consecutive_failures = 0
            except Exception as exc:
                logger.error("SERP error for keyword '%s': %s", keyword, exc)
                results.append({"keyword": keyword, "rank_position": None, "error": str(exc), "source": source})
                consecutive_failures += 1

            time.sleep(random.uniform(2, 5))

    else:
        # ── Step 2: Google blocked → fall back to DuckDuckGo ───────────────
        elapsed = time.time() - start_time
        logger.warning(
            "Google IP blocked after %.0fs probe. Switching ALL %d keywords to DuckDuckGo.",
            elapsed, len(keywords),
        )

        for keyword in keywords:
            urls = _ddg_search(keyword)
            rank = _check_domain_in_urls(domain, urls) if urls else None
            results.append({"keyword": keyword, "rank_position": rank, "source": "ddg"})
            # DDG is more lenient but still add a small delay
            time.sleep(random.uniform(0.8, 2.0))

    total_elapsed = time.time() - start_time
    found = sum(1 for r in results if r.get("rank_position") is not None)
    sources = set(r.get("source", "?") for r in results)
    logger.info(
        "SERP complete for %s: %d/%d keywords ranked (source: %s), %.0fs elapsed",
        domain, found, len(results), "+".join(sources), total_elapsed,
    )
    return results
