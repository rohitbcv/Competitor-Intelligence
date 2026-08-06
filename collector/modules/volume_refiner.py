"""
Module: Volume Refiner — pytrends differentiation within Google Ads volume buckets.

Google Keyword Planner rounds monthly search volumes to predefined tiers:
  ..., 1,300 → 1,600 → 1,900 → 2,400 → 2,900 → 3,600 → 4,400
     → 5,400 → 6,600 → 8,100 → 9,900 → 12,100 → 14,800 → 18,100 ...

When many keywords land in the same bucket they appear identical in the dashboard
(same clicks, same CTR). This module uses Google Trends relative interest scores
(0–100) to proportionally split each bucket, giving per-keyword estimates that
are more realistic while preserving the overall ±7–11% accuracy target.

Algorithm
─────────
For each bucket with ≥ 3 keywords:
  1. Designate the first keyword as the "anchor" (score = 100 baseline).
  2. Compare the anchor + up to 4 other keywords per pytrends call.
     Include the anchor in every call to normalise scores across batches.
  3. Collect a mean 12-month interest score for every keyword.
  4. Scale scores linearly to a [0.6× … 1.4×] multiplier range.
     → A keyword at max interest gets bucket_vol × 1.4
     → A keyword at min interest gets bucket_vol × 0.6
     → Single-range buckets (all equal interest) stay at bucket_vol × 1.0
  5. Keywords missing from Trends results fall back to bucket_vol (unchanged).

Rate limiting (respects AGENTS.md contract)
────────────────────────────────────────────
  • 12–18 s random delay between pytrends calls
  • On 429: wait 60 s, retry once; on second 429 skip remaining batches in bucket
  • Maximum 50 batches per refinement run (≈ 200 keywords)
"""

import time
import random
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Minimum keywords in a bucket before refinement is worth running
_MIN_BUCKET_SIZE = 3

# Keywords compared per pytrends call (anchor uses one slot → max 4 others)
_BATCH_SIZE = 4

# Random delay between calls (seconds) — keeps us under pytrends' rate limit
_INTER_BATCH_DELAY = (12, 18)

# Max batches per full refinement run (safety cap against very large keyword sets)
_MAX_BATCHES = 50

# Multiplier range applied to bucket_vol based on normalised Trends score
_MULTIPLIER_LOW  = 0.6   # keyword with lowest relative interest
_MULTIPLIER_HIGH = 1.4   # keyword with highest relative interest


def refine_volumes_with_trends(
    keyword_volumes: dict[str, int],
    geo: str = "US",
) -> dict[str, int]:
    """
    Differentiate keywords that share the same Google Ads volume bucket using
    Google Trends relative interest scores.

    Args:
        keyword_volumes: {keyword: monthly_volume} from the keyword_volumes table.
        geo:             Google Trends geo filter (default "US").

    Returns:
        Refined {keyword: monthly_volume}. Keywords in buckets smaller than
        _MIN_BUCKET_SIZE are returned unchanged. Keywords where Trends returns
        no data fall back to the original bucket value.
    """
    # Group keywords by shared bucket value
    buckets: dict[int, list[str]] = defaultdict(list)
    for kw, vol in keyword_volumes.items():
        buckets[vol].append(kw)

    refined = dict(keyword_volumes)
    total_batches = 0

    for bucket_vol, keywords in sorted(buckets.items(), key=lambda x: -len(x[1])):
        if len(keywords) < _MIN_BUCKET_SIZE:
            continue

        if total_batches >= _MAX_BATCHES:
            logger.warning(
                "[VR] Reached %d-batch limit — skipping remaining buckets.", _MAX_BATCHES
            )
            break

        logger.info(
            "[VR] Refining bucket vol=%d (%d keywords)…", bucket_vol, len(keywords)
        )

        anchor      = keywords[0]
        scores: dict[str, float] = {anchor: 100.0}
        remaining   = keywords[1:]
        consecutive_429 = 0

        for i in range(0, len(remaining), _BATCH_SIZE):
            if total_batches >= _MAX_BATCHES:
                break
            if consecutive_429 >= 2:
                logger.warning(
                    "[VR] 2 consecutive 429s on bucket %d — skipping rest of bucket.",
                    bucket_vol,
                )
                break

            batch        = remaining[i: i + _BATCH_SIZE]
            kws_to_query = [anchor] + batch

            try:
                from pytrends.request import TrendReq
                pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
                pytrends.build_payload(kws_to_query, timeframe="today 12-m", geo=geo)
                df = pytrends.interest_over_time()
                total_batches += 1

                if df is None or df.empty or anchor not in df.columns:
                    logger.warning("[VR] Empty Trends result for batch %d in bucket %d", i, bucket_vol)
                    consecutive_429 = 0
                    time.sleep(random.uniform(*_INTER_BATCH_DELAY))
                    continue

                anchor_mean = float(df[anchor].mean())
                if anchor_mean == 0:
                    consecutive_429 = 0
                    time.sleep(random.uniform(*_INTER_BATCH_DELAY))
                    continue

                for kw in batch:
                    if kw in df.columns:
                        kw_mean = float(df[kw].mean())
                        # Normalise relative to anchor so scores are comparable
                        # across batches (anchor is always 100 in our space)
                        scores[kw] = (kw_mean / anchor_mean) * 100.0

                consecutive_429 = 0

            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "rate" in err_str or "captcha" in err_str:
                    consecutive_429 += 1
                    wait = 60 * consecutive_429
                    logger.warning(
                        "[VR] pytrends 429 on batch %d (attempt %d) — waiting %ds.",
                        i, consecutive_429, wait,
                    )
                    time.sleep(wait)
                    continue   # retry same batch after wait
                else:
                    logger.warning("[VR] pytrends error on batch %d: %s", i, exc)
                    consecutive_429 = 0

            time.sleep(random.uniform(*_INTER_BATCH_DELAY))

        # ── Apply scores → refined volumes ─────────────────────────────────
        scored_kws = [kw for kw in keywords if kw in scores]
        if len(scored_kws) < 2:
            logger.info("[VR] Not enough Trends data for bucket %d — skipping.", bucket_vol)
            continue

        min_score = min(scores[kw] for kw in scored_kws)
        max_score = max(scores[kw] for kw in scored_kws)
        score_range = max_score - min_score

        for kw in scored_kws:
            if score_range > 0:
                # Normalise to [0, 1], then map to [_MULTIPLIER_LOW, _MULTIPLIER_HIGH]
                t = (scores[kw] - min_score) / score_range
            else:
                t = 0.5   # all identical → neutral multiplier (1.0)

            multiplier   = _MULTIPLIER_LOW + (_MULTIPLIER_HIGH - _MULTIPLIER_LOW) * t
            refined_vol  = max(100, int(bucket_vol * multiplier))
            refined[kw]  = refined_vol

        logger.info(
            "[VR] Bucket %d → refined %d keywords | "
            "score range %.0f–%.0f | vol range %d–%d",
            bucket_vol,
            len(scored_kws),
            min_score,
            max_score,
            int(bucket_vol * _MULTIPLIER_LOW),
            int(bucket_vol * _MULTIPLIER_HIGH),
        )

    return refined


def refine_and_save(geo: str = "US") -> int:
    """
    Run volume refinement against the full keyword_volumes table and save
    the refined values back to the database.

    Returns the number of keywords whose volume was updated.

    Called by:
      • collector/main.py  (once per scan, before traffic estimation)
      • keyword_volume_fetcher.py  (after fetching/refreshing raw volumes)
    """
    from db.sqlite import get_conn
    from datetime import datetime, timezone

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT keyword, monthly_volume FROM keyword_volumes"
        ).fetchall()

    if not rows:
        return 0

    raw_volumes = {r["keyword"]: r["monthly_volume"] for r in rows}
    refined     = refine_volumes_with_trends(raw_volumes, geo=geo)

    updated = 0
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_conn() as conn:
        for kw, new_vol in refined.items():
            old_vol = raw_volumes.get(kw, 0)
            if new_vol != old_vol:
                conn.execute(
                    """UPDATE keyword_volumes
                       SET monthly_volume = ?, updated_at = ?
                       WHERE keyword = ?""",
                    (new_vol, now, kw),
                )
                updated += 1

    logger.info("[VR] Refined and saved %d/%d keyword volumes.", updated, len(refined))
    return updated
