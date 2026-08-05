"""
Module F: DOM Change Monitor — detects page content changes via MD5 hashing.
Uses BeautifulSoup to strip dynamic elements before hashing.
"""

import hashlib
import time
import logging
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
DELAY_BETWEEN_PAGES = 1  # second

# Elements that cause false positives (dynamic content)
DYNAMIC_TAGS = ["script", "style", "noscript", "iframe", "meta", "link"]


def _compute_page_hash(html: str) -> str:
    """Strip dynamic elements and return MD5 of stable text content."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in DYNAMIC_TAGS:
        for element in soup.find_all(tag):
            element.decompose()

    # Also remove elements with common dynamic attributes
    for element in soup.find_all(attrs={"data-timestamp": True}):
        element.decompose()
    for element in soup.find_all(attrs={"data-session": True}):
        element.decompose()

    stable_text = soup.get_text(separator=" ", strip=True)
    return hashlib.md5(stable_text.encode("utf-8")).hexdigest()


def check_dom_changes(domain: str, page_urls: list[str], last_hashes: dict[str, str]) -> list[dict]:
    """
    Check whether monitored pages have changed since the last scan.

    Args:
        domain: competitor domain (for logging)
        page_urls: list of full URLs to monitor
        last_hashes: {url: last_known_hash} from database

    Returns:
        list of {
            "url": str,
            "current_hash": str,
            "has_changed": bool,
            "checked_at": str (ISO8601)
        }
    """
    results = []

    for url in page_urls:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SOHOBot/1.0)"
            })
            response.raise_for_status()

            current_hash = _compute_page_hash(response.text)
            previous_hash = last_hashes.get(url)
            has_changed = previous_hash is not None and current_hash != previous_hash

            results.append({
                "url": url,
                "current_hash": current_hash,
                "has_changed": has_changed,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            })

        except requests.exceptions.Timeout:
            logger.warning("DOM check timeout for %s", url)
            results.append({
                "url": url,
                "current_hash": "",
                "has_changed": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": "timeout",
            })
        except Exception as exc:
            logger.error("DOM check failed for %s: %s", url, exc)
            results.append({
                "url": url,
                "current_hash": "",
                "has_changed": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })

        time.sleep(DELAY_BETWEEN_PAGES)

    return results
