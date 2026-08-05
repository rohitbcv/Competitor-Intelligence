"""
Module E: Brand Interest — pytrends Google Trends data.
Returns relative search interest index (0-100), NOT traffic numbers.
"""

import time
import logging
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

BATCH_SIZE = 5  # Google Trends hard limit per request
DELAY_BETWEEN_BATCHES = 10  # seconds — required to avoid 429s


def get_brand_interest(brand_names: list[str], timeframe: str = "today 3-m") -> list[dict]:
    """
    Fetch relative search interest for a list of brand names.

    Args:
        brand_names: list of brand/hotel names (e.g., ["Marriott", "Hilton"])
        timeframe: Google Trends timeframe string (default: last 3 months)

    Returns:
        list of {
            "brand": str,
            "interest_index": int (0-100),
            "period": str
        }

    Note: This is a RELATIVE index, NOT visit counts. Do NOT display as traffic.
    """
    results = []
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))

    for i in range(0, len(brand_names), BATCH_SIZE):
        batch = brand_names[i: i + BATCH_SIZE]

        try:
            pytrends.build_payload(batch, timeframe=timeframe)
            df = pytrends.interest_over_time()

            if df.empty:
                for brand in batch:
                    results.append({"brand": brand, "interest_index": 0, "period": timeframe})
                continue

            for brand in batch:
                if brand in df.columns:
                    avg_index = int(df[brand].mean())
                else:
                    avg_index = 0
                results.append({
                    "brand": brand,
                    "interest_index": avg_index,
                    "period": timeframe,
                })

        except Exception as exc:
            error_str = str(exc).lower()
            if "429" in error_str or "rate" in error_str:
                logger.warning("pytrends rate limit. Waiting 30s then retrying batch.")
                time.sleep(30)
                try:
                    pytrends.build_payload(batch, timeframe=timeframe)
                    df = pytrends.interest_over_time()
                    for brand in batch:
                        if not df.empty and brand in df.columns:
                            results.append({
                                "brand": brand,
                                "interest_index": int(df[brand].mean()),
                                "period": timeframe,
                            })
                        else:
                            results.append({"brand": brand, "interest_index": 0, "period": timeframe})
                except Exception:
                    logger.error("pytrends retry failed for batch: %s", batch)
                    for brand in batch:
                        results.append({"brand": brand, "interest_index": 0, "period": timeframe})
            else:
                logger.error("pytrends error: %s", exc)
                for brand in batch:
                    results.append({"brand": brand, "interest_index": 0, "period": timeframe})

        if i + BATCH_SIZE < len(brand_names):
            time.sleep(DELAY_BETWEEN_BATCHES)

    return results
