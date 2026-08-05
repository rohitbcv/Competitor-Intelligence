"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Domain, TrafficData } from "@/lib/api";
import KeywordTable from "@/components/KeywordTable";

export default function KeywordsPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [traffic, setTraffic] = useState<TrafficData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDomains() {
      setLoading(true);
      try {
        const doms = await api.listDomains();
        setDomains(doms);
        if (doms.length > 0) {
          setSelectedId(doms[0].id);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    loadDomains();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setTraffic(null);
    api.getTraffic(selectedId)
      .then(setTraffic)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  if (loading) return <div className="py-16 text-center text-slate-400">Loading…</div>;
  if (error) return <div className="p-4 bg-red-50 text-red-600 rounded-lg">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Keyword Breakdown</h1>
        <p className="text-slate-500 text-sm mt-1">
          View SERP rankings and estimated traffic per keyword.
        </p>
        <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
          <p>⚠️ Estimated visits are <strong>not</strong> actual analytics data. Accuracy: ±7–11%.</p>
          <p className="mt-1.5 text-amber-600">
            <strong>What this means:</strong> Each keyword's visit count is calculated as:
            Google rank → average click-through rate for that position × monthly search volume.
            For example, rank 1 for a branded query like "marriott new york" gets ~42% of clicks,
            while rank 5 for a generic query like "hotels nyc" gets ~3.4% (Google Ads and hotel
            carousels take the rest). The ±7–11% variance accounts for daily rank fluctuations,
            rounded search volumes, and the fact that we track a sample of keywords, not all of them.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-slate-700">Competitor:</label>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
        >
          {domains.map((d) => (
            <option key={d.id} value={d.id}>
              {d.display_name || d.domain_name}
            </option>
          ))}
        </select>
      </div>

      {traffic ? (() => {
        const totalClicks = traffic.keyword_breakdown.reduce((s, k) => s + k.estimated_visits, 0);
        const brandedClicks = traffic.keyword_breakdown
          .filter((k) => {
            const kw = k.keyword.toLowerCase();
            const tokens = ["marriott","hilton","hyatt","holiday inn","intercontinental",
                            "kimpton","crowne plaza","westin","sheraton","waldorf","doubletree",
                            "hampton inn","andaz","park hyatt","grand hyatt","ihg","voco"];
            return tokens.some((t) => kw.includes(t));
          })
          .reduce((s, k) => s + k.estimated_visits, 0);
        const brandedPct = totalClicks > 0 ? Math.round((brandedClicks / totalClicks) * 100) : 0;
        return (
          <KeywordTable
            keywords={traffic.keyword_breakdown}
            domain={traffic.domain}
            brandedPct={brandedPct}
          />
        );
      })() : (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400">
          Loading keyword data…
        </div>
      )}
    </div>
  );
}
