"""Module C: SERP Rank Checker — Google primary, DuckDuckGo HTML fallback.

Strategy:
  1. Probe Google with the first keyword (short delays).
  2. If Google responds → use Google for all keywords.
  3. If Google blocks (429/empty) → fall back to DuckDuckGo HTML endpoint.
     DDG HTML is fast (~1-2s/query), requires no API key, and is less aggressively
     rate-limited. Rankings closely match Google for branded/navigational queries.
"""

import time
import random
import logging
import requests
import urllib3
from bs4 import BeautifulSoup
from googlesearch import search as google_search

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

MAX_RESULTS = 50          # Enough depth for meaningful rank signals
MAX_KEYWORDS_PER_CYCLE = 200

# Short backoffs for the IP-block probe
PROBE_DELAYS = [5, 10]
# Normal backoffs once Google is responding
BACKOFF_DELAYS = [5, 15, 30]
MAX_CONSECUTIVE_FAILURES = 2

_DDG_URL = "https://html.duckduckgo.com/html/"
_DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://duckduckgo.com/",
}


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


# ── DuckDuckGo HTML helpers ─────────────────────────────────────────────────

def _ddg_html_search(query: str, num: int = MAX_RESULTS) -> list[str]:
    """
    Query DuckDuckGo's lightweight HTML endpoint directly.
    Faster and more reliable than the ddgs library on CI/cloud IPs.
    Falls back gracefully on any error.
    Retries once on 202 (DDG soft rate-limit) with a 5-second back-off.
    """
    urls = []
    for attempt in range(2):
        try:
            data = {"q": query, "b": "", "kl": "us-en"}
            resp = requests.post(
                _DDG_URL, data=data, headers=_DDG_HEADERS, timeout=20, verify=False,
            )
            if resp.status_code == 202:
                # Soft rate-limit — wait and retry once
                if attempt == 0:
                    logger.debug("DDG 202 for '%s', backing off 5s then retrying.", query)
                    time.sleep(5)
                    continue
                logger.warning("DDG HTML still 202 after retry for '%s' — skipping.", query)
                return []
            if resp.status_code != 200:
                logger.warning("DDG HTML returned %d for '%s'", resp.status_code, query)
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select(".result__url"):
                href = a.get("href") or a.text.strip()
                if href and ("http" in href or "." in href):
                    urls.append(href)
                    if len(urls) >= num:
                        break
            return urls
        except Exception as exc:
            logger.warning("DDG HTML search failed for '%s': %s", query, exc)
            return []
    return urls


# ── Shared helpers ──────────────────────────────────────────────────────────

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
      - If Google blocks → switch to DuckDuckGo HTML for all keywords.
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
        # Google is accessible — use it for all keywords
        logger.info("Google accessible for %s. Using Google SERP.", domain)
        source = "google"
        rank = _check_domain_in_urls(domain, probe_urls)
        results.append({"keyword": probe_kw, "rank_position": rank, "source": source})
        consecutive_failures = 0
        time.sleep(random.uniform(2, 5))

        for keyword in keywords[1:]:
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "%d consecutive Google failures for %s — switching remaining to DDG.",
                    consecutive_failures, domain,
                )
                for remaining in keywords[len(results):]:
                    urls = _ddg_html_search(remaining)
                    rank = _check_domain_in_urls(domain, urls) if urls else None
                    results.append({"keyword": remaining, "rank_position": rank, "source": "ddg"})
                    time.sleep(random.uniform(0.8, 1.5))
                break

            try:
                urls = _google_search_with_backoff(keyword, delays=BACKOFF_DELAYS)
                if not urls:
                    results.append({"keyword": keyword, "rank_position": None,
                                    "skipped": "blocked", "source": source})
                    consecutive_failures += 1
                else:
                    rank = _check_domain_in_urls(domain, urls)
                    results.append({"keyword": keyword, "rank_position": rank, "source": source})
                    consecutive_failures = 0
            except Exception as exc:
                logger.error("SERP error for keyword '%s': %s", keyword, exc)
                results.append({"keyword": keyword, "rank_position": None,
                                "error": str(exc), "source": source})
                consecutive_failures += 1

            time.sleep(random.uniform(2, 5))

    else:
        # ── Step 2: Google blocked → use DuckDuckGo HTML for everything ────
        elapsed = time.time() - start_time
        logger.warning(
            "Google IP blocked after %.0fs probe. Switching ALL %d keywords to DDG HTML.",
            elapsed, len(keywords),
        )
        for keyword in keywords:
            urls = _ddg_html_search(keyword)
            rank = _check_domain_in_urls(domain, urls) if urls else None
            results.append({"keyword": keyword, "rank_position": rank, "source": "ddg"})
            # 2-3s delay between DDG queries to avoid soft rate-limiting (202 responses)
            time.sleep(random.uniform(2.0, 3.5))

    total_elapsed = time.time() - start_time
    found = sum(1 for r in results if r.get("rank_position") is not None)
    sources = set(r.get("source", "?") for r in results)
    logger.info(
        "SERP complete for %s: %d/%d keywords ranked (source: %s), %.0fs elapsed",
        domain, found, len(results), "+".join(sources), total_elapsed,
    )
    return results
