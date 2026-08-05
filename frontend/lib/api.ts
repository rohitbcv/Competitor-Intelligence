const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export type Domain = {
  id: string;
  domain_name: string;
  display_name: string | null;
  client_id: string | null;
  is_active: boolean;
  created_at: string;
};

export type KeywordEstimate = {
  keyword: string;
  monthly_volume: number;
  serp_rank: number | null;
  ctr: number;
  estimated_visits: number;
  delta_visits: number;
  delta_pct: number;
};

export type TrafficData = {
  domain: string;
  domain_id: string;
  total_estimated_monthly_visits: number;
  keywords_tracked: number;
  keyword_breakdown: KeywordEstimate[];
  accuracy: string;
  data_disclaimer: string;
};

export type TrendPoint = { week: string; est_traffic: number };

export type TechProfile = {
  domain_id: string;
  technologies: string[];
  scan_status: string;
  scraped_at: string;
};

export type TechHistoryItem = {
  scraped_at: string;
  technologies: string[];
  added: string[];
  removed: string[];
};

export type SitemapData = {
  domain_id: string;
  total_pages: number;
  page_growth_4w: number;
  last_modified: string | null;
  scanned_at: string;
};

export type ChangeEvent = {
  page_url: string;
  has_changed: boolean;
  html_hash: string;
  checked_at: string;
};

export type ChangesData = {
  domain_id: string;
  total_monitored_pages: number;
  changed_count: number;
  events: ChangeEvent[];
};

export type OverviewData = {
  domain: string;
  display_name: string | null;
  traffic: {
    total_estimated_monthly_visits: number;
    keywords_tracked: number;
    top_keywords: KeywordEstimate[];
    accuracy: string;
  };
  tech_stack: {
    current: string[];
    changes_since_last_scan: { added: string[]; removed: string[] };
  };
  sitemap: { total_pages: number; last_modified: string | null };
  dom_changes: { changed_pages: number; monitored_pages: number; last_change: string | null };
  last_scan: string | null;
  data_disclaimer: string;
};

export type CompareItem = {
  domain_id: string;
  domain: string;
  display_name: string | null;
  total_estimated_monthly_visits: number;
  keywords_tracked: number;
  technologies: string[];
};

// API functions
export const api = {
  listDomains: () => apiFetch<Domain[]>("/api/domains"),
  addDomain: (payload: { domain_name: string; display_name?: string }) =>
    apiFetch<Domain>("/api/domains", { method: "POST", body: JSON.stringify(payload) }),
  removeDomain: (id: string) =>
    apiFetch<void>(`/api/domains/${id}`, { method: "DELETE" }),
  getOverview: (id: string) => apiFetch<OverviewData>(`/api/domains/${id}/overview`),
  getTraffic: (id: string) => apiFetch<TrafficData>(`/api/domains/${id}/traffic`),
  getTrafficTrend: (id: string) => apiFetch<TrendPoint[]>(`/api/domains/${id}/traffic/trend`),
  getTech: (id: string) => apiFetch<TechProfile>(`/api/domains/${id}/tech`),
  getTechHistory: (id: string) => apiFetch<TechHistoryItem[]>(`/api/domains/${id}/tech/history`),
  getSitemap: (id: string) => apiFetch<SitemapData>(`/api/domains/${id}/sitemap`),
  getChanges: (id: string) => apiFetch<ChangesData>(`/api/domains/${id}/changes`),
  compare: (ids: string[]) => apiFetch<CompareItem[]>(`/api/compare?domains=${ids.join(",")}`),
  triggerScan: (domainId: string) =>
    apiFetch<{ status: string; message: string }>(`/api/scan/trigger?domain_id=${domainId}`, {
      method: "POST",
    }),
  getScanStatus: (domainId: string) =>
    apiFetch<{ status: string; progress_pct: number; current_module_label: string; modules_done_labels: string[]; error?: string }>(`/api/scan/status/${domainId}`),
};
