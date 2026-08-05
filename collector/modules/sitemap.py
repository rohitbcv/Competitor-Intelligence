"""Module A: Sitemap Engine — parses competitor sitemaps using advertools."""

import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
import advertools as adv
import pandas as pd

# Patch urllib's default SSL context to bypass corporate proxy cert verification.
# Required on networks with SSL inspection (e.g. RateGainForwardTrustCAECDSA proxy).
_no_verify_ctx = ssl.create_default_context()
_no_verify_ctx.check_hostname = False
_no_verify_ctx.verify_mode = ssl.CERT_NONE
urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.HTTPSHandler(context=_no_verify_ctx))
)

_SITEMAP_TIMEOUT_SECS = 45   # give up if advertools hangs longer than this


def _fetch_sitemap_df(sitemap_url: str) -> pd.DataFrame:
    return adv.sitemap_to_df(sitemap_url)


def parse_sitemap(domain: str) -> dict:
    """
    Parse the sitemap for a given domain.

    Returns:
        {
            "total_pages": int,
            "last_modified": datetime | None,
            "urls": list[str]
        }
        or {"error": "no_sitemap"} if no sitemap.xml found.
    """
    sitemap_url = f"https://{domain}/sitemap.xml"
    try:
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_fetch_sitemap_df, sitemap_url)
        try:
            df: pd.DataFrame = future.result(timeout=_SITEMAP_TIMEOUT_SECS)
        except FuturesTimeoutError:
            pool.shutdown(wait=False)   # don't block — let the hung thread die on its own
            return {"error": f"timeout after {_SITEMAP_TIMEOUT_SECS}s"}
        finally:
            pool.shutdown(wait=False)

        if df is None or df.empty:
            return {"error": "no_sitemap"}

        urls = df["loc"].dropna().tolist() if "loc" in df.columns else []
        total_pages = len(urls)

        last_modified = None
        if "lastmod" in df.columns:
            valid_dates = df["lastmod"].dropna()
            if not valid_dates.empty:
                try:
                    last_modified = pd.to_datetime(valid_dates).max()
                    if hasattr(last_modified, "to_pydatetime"):
                        last_modified = last_modified.to_pydatetime()
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                except Exception:
                    last_modified = None

        return {
            "total_pages": total_pages,
            "last_modified": last_modified,
            "urls": urls[:500],  # cap URL list to avoid memory issues
        }

    except Exception as exc:
        error_msg = str(exc).lower()
        if "404" in error_msg or "not found" in error_msg or "no sitemap" in error_msg:
            return {"error": "no_sitemap"}
        return {"error": str(exc)}
