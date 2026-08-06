"""
Competitor Intelligence Tracker — Main Collector Orchestrator

Runs all 6 data collection modules for each tracked domain.
Triggered weekly by GitHub Actions cron (see .github/workflows/scrape.yml).
"""

import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from collector.db import client as db
from collector.modules.sitemap import parse_sitemap
from collector.modules.tech_stack import detect_tech_stack
from collector.modules.serp_checker import check_serp_ranks
from collector.modules.traffic_estimator import estimate_traffic
from collector.modules.brand_interest import get_brand_interest
from collector.modules.dom_monitor import check_dom_changes
from collector.modules.keyword_volume_fetcher import refresh_volumes_in_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("collector.main")


def _error_response(module: str, domain: str, error_type: str, message: str) -> dict:
    return {
        "status": "error",
        "module": module,
        "domain": domain,
        "error_type": error_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def scan_domain(domain_row: dict, keywords: list[str], keyword_volumes: dict[str, int],
                status_callback=None) -> dict:
    """Run all 6 modules for a single domain. Returns a summary dict.
    
    status_callback(module_name): called before each module starts, used by the
    API scan router to update the in-memory progress registry.
    """
    domain_id = domain_row["id"]
    domain = domain_row["domain_name"]
    display = domain_row.get("display_name", domain)
    scan_results: dict = {"domain": domain, "display_name": display}

    def _notify(module: str):
        if status_callback:
            status_callback(module)

    logger.info("── Starting scan for %s ──", domain)

    # ── Module A: Sitemap ──────────────────────────────────────────────────
    try:
        _notify("sitemap")
        logger.info("[A] Sitemap: %s", domain)
        sitemap_data = parse_sitemap(domain)
        scan_results["sitemap"] = sitemap_data

        if "error" not in sitemap_data:
            db.upsert_sitemap_metrics(
                domain_id=domain_id,
                total_pages=sitemap_data["total_pages"],
                last_modified=sitemap_data.get("last_modified"),
            )
        else:
            logger.warning("[A] No sitemap for %s: %s", domain, sitemap_data["error"])

    except Exception as exc:
        err = _error_response("sitemap", domain, "unknown", str(exc))
        scan_results["sitemap"] = err
        db.log_scan_error(domain_id, "sitemap", "unknown", str(exc))

    # ── Module B: Tech Stack ───────────────────────────────────────────────
    try:
        _notify("tech_stack")
        logger.info("[B] Tech stack: %s", domain)
        tech_data = detect_tech_stack(domain)
        scan_results["tech"] = tech_data

        db.upsert_tech_profile(
            domain_id=domain_id,
            detected_tech=tech_data["technologies"],
            scan_status=tech_data["scan_status"],
        )

    except Exception as exc:
        err = _error_response("tech_stack", domain, "unknown", str(exc))
        scan_results["tech"] = err
        db.log_scan_error(domain_id, "tech_stack", "unknown", str(exc))

    # ── Module C: SERP Ranks ───────────────────────────────────────────────
    serp_results = []
    try:
        _notify("serp_checker")
        logger.info("[C] SERP ranks: %s (%d keywords)", domain, len(keywords))
        serp_results = check_serp_ranks(domain, keywords)
        scan_results["serp"] = serp_results

        for item in serp_results:
            db.upsert_keyword_ranking(
                domain_id=domain_id,
                keyword=item["keyword"],
                rank_position=item.get("rank_position"),
            )

    except Exception as exc:
        err = _error_response("serp_checker", domain, "unknown", str(exc))
        scan_results["serp"] = err
        db.log_scan_error(domain_id, "serp_checker", "unknown", str(exc))

    # ── Module D: Traffic Estimator ────────────────────────────────────────
    try:
        _notify("traffic_estimator")
        logger.info("[D] Traffic estimate: %s", domain)
        traffic_data = estimate_traffic(domain, serp_results, keyword_volumes)
        scan_results["traffic"] = traffic_data

        # Only persist estimates when we have at least some real SERP ranks.
        # Saving all-zero rows when SERP is blocked would overwrite good historical data.
        ranked_count = sum(
            1 for item in traffic_data["keyword_breakdown"]
            if item.get("serp_rank") is not None
        )
        if ranked_count == 0:
            logger.warning(
                "[D] Skipping traffic estimate save for %s — SERP returned 0 ranked keywords "
                "(IP likely blocked). Existing estimates preserved.", domain
            )
        else:
            for item in traffic_data["keyword_breakdown"]:
                db.upsert_traffic_estimate(
                    domain_id=domain_id,
                    keyword=item["keyword"],
                    monthly_search_volume=item["monthly_volume"],
                    serp_rank=item.get("serp_rank"),
                    estimated_ctr=item["ctr"],
                    estimated_monthly_visits=item["estimated_visits"],
                )

    except Exception as exc:
        err = _error_response("traffic_estimator", domain, "unknown", str(exc))
        scan_results["traffic"] = err
        db.log_scan_error(domain_id, "traffic_estimator", "unknown", str(exc))

    # ── Module E: Brand Interest ───────────────────────────────────────────
    try:
        _notify("brand_interest")
        brand_name = display or domain
        logger.info("[E] Brand interest: %s", brand_name)
        interest_data = get_brand_interest([brand_name])
        scan_results["brand_interest"] = interest_data

    except Exception as exc:
        err = _error_response("brand_interest", domain, "unknown", str(exc))
        scan_results["brand_interest"] = err
        db.log_scan_error(domain_id, "brand_interest", "unknown", str(exc))

    # ── Module F: DOM Change Monitor ───────────────────────────────────────
    try:
        _notify("dom_monitor")
        logger.info("[F] DOM monitor: %s", domain)
        homepage_url = f"https://{domain}"
        last_hashes = {
            homepage_url: db.get_last_dom_hash(domain_id, homepage_url) or ""
        }
        dom_results = check_dom_changes(domain, [homepage_url], last_hashes)
        scan_results["dom"] = dom_results

        for item in dom_results:
            if item.get("current_hash"):
                db.upsert_site_change(
                    domain_id=domain_id,
                    page_url=item["url"],
                    html_hash=item["current_hash"],
                    has_changed=item["has_changed"],
                )

    except Exception as exc:
        err = _error_response("dom_monitor", domain, "unknown", str(exc))
        scan_results["dom"] = err
        db.log_scan_error(domain_id, "dom_monitor", "unknown", str(exc))

    logger.info("── Scan complete for %s ──", domain)
    return scan_results


def main():
    logger.info("=== Competitor Intelligence Tracker — Scan Started ===")
    logger.info("Timestamp: %s", datetime.now(timezone.utc).isoformat())

    domains = db.get_active_domains()
    if not domains:
        logger.warning("No active domains found. Exiting.")
        return

    logger.info("Found %d active domains.", len(domains))

    # Refresh keyword volumes from Google Ads API if credentials are configured.
    # Silently skipped when google-ads.yaml is absent or incomplete.
    refreshed = refresh_volumes_in_db()
    if refreshed:
        logger.info("Refreshed %d keyword volumes from Google Ads Keyword Planner.", refreshed)
    else:
        logger.info("Using stored keyword volumes (Google Ads API not configured).")

    keyword_volumes = db.get_keyword_volumes()
    keywords = list(keyword_volumes.keys())
    logger.info("Loaded %d keywords from keyword_volumes table.", len(keywords))

    all_results = []
    for domain_row in domains:
        try:
            result = scan_domain(domain_row, keywords, keyword_volumes)
            all_results.append(result)
        except Exception as exc:
            logger.error("Fatal error scanning domain %s: %s", domain_row.get("domain_name"), exc)
            db.log_scan_error(domain_row["id"], "orchestrator", "unknown", str(exc))

    logger.info("=== Scan Complete. Processed %d domains. ===", len(all_results))


if __name__ == "__main__":
    main()
