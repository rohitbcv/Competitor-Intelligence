-- ============================================================
-- Competitor Intelligence Tracker — Supabase Schema
-- Run this entire file in your Supabase SQL Editor
-- ============================================================

-- 1. Domains (master list of tracked competitors)
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    client_id UUID,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tech Stack Snapshots
CREATE TABLE IF NOT EXISTS tech_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    detected_tech JSONB NOT NULL,
    scan_status VARCHAR(20) DEFAULT 'success',  -- success | blocked | error
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Keyword Rankings
CREATE TABLE IF NOT EXISTS keyword_rankings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    rank_position INT,  -- NULL if not found in top 100
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Traffic Estimates
CREATE TABLE IF NOT EXISTS traffic_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    monthly_search_volume INT NOT NULL,
    serp_rank INT,
    estimated_ctr DECIMAL(6,4),
    estimated_monthly_visits INT NOT NULL DEFAULT 0,
    estimated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Sitemap Metrics
CREATE TABLE IF NOT EXISTS sitemap_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    total_pages INT NOT NULL,
    last_modified TIMESTAMPTZ,
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. DOM Change Log
CREATE TABLE IF NOT EXISTS site_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id) ON DELETE CASCADE,
    page_url TEXT NOT NULL,
    html_hash VARCHAR(32) NOT NULL,
    has_changed BOOLEAN DEFAULT FALSE,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Search Volume Reference (populated from CSV upload)
CREATE TABLE IF NOT EXISTS keyword_volumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword VARCHAR(255) UNIQUE NOT NULL,
    monthly_volume INT NOT NULL,
    competition VARCHAR(20),  -- HIGH | MEDIUM | LOW
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Scan Errors
CREATE TABLE IF NOT EXISTS scan_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id),
    module VARCHAR(50) NOT NULL,
    error_type VARCHAR(50),
    error_message TEXT,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Aggregate Views
-- ============================================================

-- Dashboard summary: total estimated traffic per domain
CREATE OR REPLACE VIEW domain_traffic_summary AS
SELECT
    d.domain_name,
    d.display_name,
    SUM(te.estimated_monthly_visits) AS total_est_monthly_traffic,
    COUNT(DISTINCT te.keyword) AS keywords_tracked,
    AVG(te.estimated_ctr) AS avg_ctr,
    MAX(te.estimated_at) AS last_scan
FROM domains d
LEFT JOIN traffic_estimates te ON d.id = te.domain_id
WHERE d.is_active = TRUE
GROUP BY d.domain_name, d.display_name;

-- Week-over-week traffic trend
CREATE OR REPLACE VIEW traffic_trend AS
SELECT
    d.domain_name,
    DATE_TRUNC('week', te.estimated_at) AS week,
    SUM(te.estimated_monthly_visits) AS est_traffic
FROM domains d
JOIN traffic_estimates te ON d.id = te.domain_id
GROUP BY d.domain_name, DATE_TRUNC('week', te.estimated_at)
ORDER BY week DESC;

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_traffic_domain ON traffic_estimates(domain_id);
CREATE INDEX IF NOT EXISTS idx_traffic_keyword ON traffic_estimates(keyword);
CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic_estimates(estimated_at);
CREATE INDEX IF NOT EXISTS idx_rankings_domain ON keyword_rankings(domain_id);
CREATE INDEX IF NOT EXISTS idx_sitemap_domain ON sitemap_metrics(domain_id);
CREATE INDEX IF NOT EXISTS idx_changes_domain ON site_changes(domain_id);
CREATE INDEX IF NOT EXISTS idx_errors_domain ON scan_errors(domain_id);
