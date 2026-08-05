"""Pydantic schemas for the Competitor Intelligence Tracker API."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ── Domains ───────────────────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    domain_name: str
    display_name: str | None = None
    client_id: str | None = None


class DomainResponse(BaseModel):
    id: str
    domain_name: str
    display_name: str | None
    client_id: str | None
    is_active: bool
    created_at: datetime


# ── Traffic ───────────────────────────────────────────────────────────────────

class KeywordEstimate(BaseModel):
    keyword: str
    monthly_volume: int
    serp_rank: int | None
    ctr: float
    estimated_visits: int


class TrafficResponse(BaseModel):
    domain_id: str
    total_estimated_monthly_visits: int
    keywords_tracked: int
    keyword_breakdown: list[KeywordEstimate]
    accuracy: str = "estimate_30_50_pct_variance"
    data_disclaimer: str = (
        "All traffic figures are estimates with +/-30-50% variance. "
        "They do not represent actual analytics."
    )


class TrafficTrendPoint(BaseModel):
    week: str
    est_traffic: int


# ── Tech Stack ─────────────────────────────────────────────────────────────────

class TechProfileResponse(BaseModel):
    domain_id: str
    technologies: list[str]
    scan_status: str
    scraped_at: datetime


class TechHistoryItem(BaseModel):
    scraped_at: datetime
    technologies: list[str]
    added: list[str]
    removed: list[str]


# ── Sitemap ───────────────────────────────────────────────────────────────────

class SitemapResponse(BaseModel):
    domain_id: str
    total_pages: int
    last_modified: datetime | None
    scanned_at: datetime


# ── DOM Changes ───────────────────────────────────────────────────────────────

class ChangeEvent(BaseModel):
    page_url: str
    has_changed: bool
    checked_at: datetime


# ── Overview ──────────────────────────────────────────────────────────────────

class OverviewResponse(BaseModel):
    domain: str
    display_name: str | None
    traffic: dict[str, Any]
    tech_stack: dict[str, Any]
    sitemap: dict[str, Any]
    dom_changes: dict[str, Any]
    last_scan: datetime | None
    data_disclaimer: str = (
        "All traffic figures are estimates with +/-30-50% variance. "
        "They do not represent actual analytics."
    )


# ── Keyword Upload ────────────────────────────────────────────────────────────

class KeywordUploadResponse(BaseModel):
    inserted: int
    updated: int
    errors: int


# ── Scan Trigger ─────────────────────────────────────────────────────────────

class ScanTriggerResponse(BaseModel):
    status: str = "accepted"
    domain_id: str
    message: str
