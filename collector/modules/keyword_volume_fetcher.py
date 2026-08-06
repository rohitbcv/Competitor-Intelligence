"""
Module: Keyword Volume Fetcher — Google Ads Keyword Planner API

Fetches REAL monthly search volumes for all keywords in the keyword_volumes table
using Google's KeywordPlanIdeaService. Replaces hardcoded volume estimates with
actual Google data.

Setup required (one-time):
  1. Google Ads account at https://ads.google.com
  2. Developer token from https://ads.google.com/aw/apicenter  (needs Basic Access)
  3. OAuth2 credentials from https://console.cloud.google.com
  4. Run: python collector/modules/keyword_volume_fetcher.py --auth
     to generate the refresh_token interactively
  5. Fill in google-ads.yaml (see .env.example for template)

Once configured, this module is called automatically at the start of every scan
to keep volumes up to date.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the google-ads YAML config (sits at project root)
_YAML_PATH = Path(__file__).parent.parent.parent / "google-ads.yaml"

# Google Ads API keyword volume batch limit
_BATCH_SIZE = 20   # API allows up to 20 keywords per request


def _is_configured() -> bool:
    """Return True if google-ads.yaml exists and has required fields filled."""
    if not _YAML_PATH.exists():
        return False
    content = _YAML_PATH.read_text()
    required = ["developer_token", "client_id", "client_secret", "refresh_token", "login_customer_id"]
    return all(f"{field}:" in content and "YOUR_" not in content.split(f"{field}:")[1].split("\n")[0]
               for field in required)


def fetch_keyword_volumes(keywords: list[str]) -> dict[str, int]:
    """
    Fetch real monthly search volumes from Google Ads Keyword Planner.

    Args:
        keywords: list of keyword strings to look up

    Returns:
        dict mapping keyword → average_monthly_searches (int)
        Returns empty dict if API is not configured or call fails.

    The returned volumes are 12-month averages from Google's own data —
    the same numbers shown in Google Keyword Planner.
    """
    if not keywords:
        return {}

    if not _is_configured():
        logger.info(
            "[KV] google-ads.yaml not configured — skipping live volume fetch. "
            "See collector/modules/keyword_volume_fetcher.py for setup instructions."
        )
        return {}

    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException

        client = GoogleAdsClient.load_from_storage(str(_YAML_PATH))
        customer_id = _get_customer_id(client)

        idea_service = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = client.get_service("GoogleAdsService").language_constant_path("1000")  # English
        request.include_adult_keywords = False
        request.keyword_plan_network = (
            client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        )

        volumes: dict[str, int] = {}

        # Process in batches of 20 (API limit)
        for i in range(0, len(keywords), _BATCH_SIZE):
            batch = keywords[i : i + _BATCH_SIZE]

            request.keyword_seed.keywords[:] = batch

            try:
                response = idea_service.generate_keyword_ideas(request=request)
                for idea in response:
                    kw = idea.text.lower().strip()
                    avg = idea.keyword_idea_metrics.avg_monthly_searches
                    if kw in [k.lower() for k in batch]:
                        volumes[kw] = int(avg)

                logger.info("[KV] Fetched volumes for batch %d/%d (%d keywords)",
                            i // _BATCH_SIZE + 1,
                            (len(keywords) + _BATCH_SIZE - 1) // _BATCH_SIZE,
                            len(batch))

            except GoogleAdsException as gae:
                logger.error("[KV] Google Ads API error for batch: %s", gae)

        logger.info("[KV] Fetched real volumes for %d/%d keywords", len(volumes), len(keywords))
        return volumes

    except Exception as exc:
        logger.error("[KV] Unexpected error fetching keyword volumes: %s", exc)
        return {}


def _get_customer_id(client) -> str:
    """Extract customer_id from the YAML config."""
    content = _YAML_PATH.read_text()
    for line in content.splitlines():
        if "login_customer_id:" in line:
            return line.split("login_customer_id:")[-1].strip().replace("-", "")
    raise ValueError("login_customer_id not found in google-ads.yaml")


def refresh_volumes_in_db() -> int:
    """
    Fetch live volumes from Google Ads and update the keyword_volumes table.

    Returns the number of keywords updated. Called once per scan run.
    """
    if not _is_configured():
        return 0

    from db.sqlite import get_conn

    with get_conn() as conn:
        rows = conn.execute("SELECT keyword FROM keyword_volumes").fetchall()
        keywords = [r[0] for r in rows]

    if not keywords:
        return 0

    live_volumes = fetch_keyword_volumes(keywords)
    if not live_volumes:
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = 0

    with get_conn() as conn:
        for keyword, volume in live_volumes.items():
            conn.execute(
                """UPDATE keyword_volumes
                   SET monthly_volume = ?, updated_at = ?
                   WHERE LOWER(keyword) = LOWER(?)""",
                (volume, now, keyword),
            )
            updated += conn.execute("SELECT changes()").fetchone()[0]

    logger.info("[KV] Updated %d keyword volumes with real Google Ads data.", updated)
    return updated


def setup_auth():
    """
    Interactive OAuth2 flow to generate a refresh_token.
    Run this once from the command line:
        python collector/modules/keyword_volume_fetcher.py --auth
    """
    import json
    import webbrowser
    from urllib.parse import urlparse, parse_qs

    print("\n=== Google Ads OAuth2 Setup ===")
    print("You need your client_id and client_secret from Google Cloud Console.")
    print("https://console.cloud.google.com → Credentials → OAuth 2.0 Client IDs\n")

    client_id     = input("Enter client_id: ").strip()
    client_secret = input("Enter client_secret: ").strip()

    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={client_id}"
        "&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/adwords"
        "&access_type=offline"
        "&prompt=consent"
    )

    print(f"\nOpening browser for authorization…\n{auth_url}")
    webbrowser.open(auth_url)

    auth_code = input("\nPaste the authorization code shown in the browser: ").strip()

    import urllib.request
    import urllib.parse

    token_data = urllib.parse.urlencode({
        "code":          auth_code,
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uri":  "urn:ietf:wg:oauth:2.0:oob",
        "grant_type":    "authorization_code",
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("ERROR: No refresh_token returned. Make sure you enabled 'access_type=offline'.")
        return

    print(f"\n✅ Got refresh_token: {refresh_token}")
    print("\nAdd these to your google-ads.yaml:")
    print(f"  client_id: {client_id}")
    print(f"  client_secret: {client_secret}")
    print(f"  refresh_token: {refresh_token}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--auth" in sys.argv:
        setup_auth()
    else:
        print("Usage: python keyword_volume_fetcher.py --auth")
        print("       to generate your OAuth2 refresh token")
