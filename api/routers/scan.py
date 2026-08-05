"""
Scan trigger router — manual scan for a single domain (dev/test only).
POST /api/scan/trigger
GET  /api/scan/status/{domain_id}
"""

import logging
import threading
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from db.sqlite import get_conn, row_to_dict

router = APIRouter(prefix="/api/scan", tags=["scan"])
logger = logging.getLogger(__name__)

SCAN_REGISTRY: dict[str, dict] = {}
_registry_lock = threading.Lock()

MODULES = ["sitemap", "tech_stack", "serp_checker", "traffic_estimator", "brand_interest", "dom_monitor"]


def _update_status(domain_id: str, **kwargs):
    with _registry_lock:
        if domain_id in SCAN_REGISTRY:
            SCAN_REGISTRY[domain_id].update(kwargs)


def _get_done(domain_id: str, current_module: str) -> list[str]:
    idx = MODULES.index(current_module) if current_module in MODULES else 0
    return MODULES[:idx]


def _run_scan_background(domain_id: str, domain_name: str):
    from collector.db import client as db
    from collector.main import scan_domain

    _update_status(domain_id, status="running", current_module="loading", modules_done=[])

    try:
        with get_conn() as conn:
            domain_row = row_to_dict(conn.execute(
                "SELECT * FROM domains WHERE id=?", (domain_id,)
            ).fetchone())

        if not domain_row:
            _update_status(domain_id, status="error", error="Domain not found")
            return

        keyword_volumes = db.get_keyword_volumes()
        keywords = list(keyword_volumes.keys())

        _update_status(domain_id, current_module="sitemap")
        scan_domain(
            domain_row, keywords, keyword_volumes,
            status_callback=lambda mod: _update_status(
                domain_id,
                current_module=mod,
                modules_done=_get_done(domain_id, mod),
            ),
        )

        _update_status(
            domain_id,
            status="complete",
            current_module=None,
            modules_done=MODULES,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Scan complete for %s", domain_name)

    except Exception as exc:
        logger.error("Scan failed for %s: %s", domain_name, exc)
        _update_status(domain_id, status="error", error=str(exc))


@router.post("/trigger")
async def trigger_scan(domain_id: str, background_tasks: BackgroundTasks):
    with get_conn() as conn:
        domain = row_to_dict(conn.execute(
            "SELECT id, domain_name FROM domains WHERE id=?", (domain_id,)
        ).fetchone())

    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain_name = domain["domain_name"]

    with _registry_lock:
        SCAN_REGISTRY[domain_id] = {
            "domain_id": domain_id,
            "domain_name": domain_name,
            "status": "queued",
            "current_module": None,
            "modules_done": [],
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

    background_tasks.add_task(_run_scan_background, domain_id, domain_name)

    return {
        "status": "accepted",
        "domain_id": domain_id,
        "message": f"Scan queued for {domain_name}",
    }


@router.get("/status/{domain_id}")
async def get_scan_status(domain_id: str):
    with _registry_lock:
        entry = SCAN_REGISTRY.get(domain_id)

    if not entry:
        return {
            "domain_id": domain_id,
            "status": "idle",
            "message": "No scan has been triggered for this domain in this session.",
        }

    total = len(MODULES)
    done = len(entry.get("modules_done", []))

    module_labels = {
        "sitemap": "Sitemap (A)",
        "tech_stack": "Tech Stack (B)",
        "serp_checker": "SERP Rankings (C)",
        "traffic_estimator": "Traffic Estimator (D)",
        "brand_interest": "Brand Interest (E)",
        "dom_monitor": "DOM Monitor (F)",
        None: None,
    }

    current = entry.get("current_module")
    return {
        **entry,
        "progress_pct": int((done / total) * 100),
        "current_module_label": module_labels.get(current, current),
        "modules_done_labels": [module_labels.get(m, m) for m in entry.get("modules_done", [])],
    }
