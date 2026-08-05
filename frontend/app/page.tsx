"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Domain, OverviewData } from "@/lib/api";
import OverviewCard from "@/components/OverviewCard";

type ScanStatus = {
  status: "idle" | "queued" | "running" | "complete" | "error";
  current_module_label?: string;
  modules_done_labels?: string[];
  progress_pct?: number;
  error?: string;
  completed_at?: string;
};

const MODULE_LABELS = [
  "Sitemap (A)",
  "Tech Stack (B)",
  "SERP Rankings (C)",
  "Traffic Estimator (D)",
  "Brand Interest (E)",
  "DOM Monitor (F)",
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function OverviewPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [overviews, setOverviews] = useState<Record<string, OverviewData>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newDomain, setNewDomain] = useState("");
  const [adding, setAdding] = useState(false);
  const [scanStatuses, setScanStatuses] = useState<Record<string, ScanStatus>>({});
  const pollersRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  async function load() {
    setLoading(true);
    try {
      const doms = await api.listDomains();
      setDomains(doms);
      const results = await Promise.allSettled(doms.map((d) => api.getOverview(d.id)));
      const map: Record<string, OverviewData> = {};
      results.forEach((r, i) => {
        if (r.status === "fulfilled") map[doms[i].id] = r.value;
      });
      setOverviews(map);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Clean up pollers on unmount
  useEffect(() => {
    return () => {
      Object.values(pollersRef.current).forEach(clearInterval);
    };
  }, []);

  function startPolling(domainId: string) {
    if (pollersRef.current[domainId]) clearInterval(pollersRef.current[domainId]);

    const poll = async () => {
      try {
        const resp = await fetch(`${API_URL}/api/scan/status/${domainId}`);
        const data: ScanStatus = await resp.json();
        setScanStatuses((prev) => ({ ...prev, [domainId]: data }));

        if (data.status === "complete" || data.status === "error") {
          clearInterval(pollersRef.current[domainId]);
          delete pollersRef.current[domainId];
          // Reload overview data once scan completes
          if (data.status === "complete") {
            const overview = await api.getOverview(domainId);
            setOverviews((prev) => ({ ...prev, [domainId]: overview }));
          }
        }
      } catch {}
    };

    poll(); // immediate first call
    pollersRef.current[domainId] = setInterval(poll, 3000);
  }

  function normalizeDomain(raw: string): string {
    raw = raw.trim().toLowerCase();
    if (!raw) return raw;
    try {
      if (!raw.includes("://")) raw = "https://" + raw;
      const host = new URL(raw).hostname;
      return host.startsWith("www.") ? host.slice(4) : host;
    } catch {
      // URL parse failed — strip obvious protocol/www manually
      return raw.replace(/^https?:\/\//i, "").replace(/^www\./i, "").split("/")[0];
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newDomain.trim()) return;
    setAdding(true);
    try {
      const normalized = normalizeDomain(newDomain);
      await api.addDomain({ domain_name: normalized });
      setNewDomain("");
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function handleScan(domainId: string) {
    try {
      setScanStatuses((prev) => ({ ...prev, [domainId]: { status: "queued", progress_pct: 0 } }));
      await api.triggerScan(domainId);
      startPolling(domainId);
    } catch (e: any) {
      setScanStatuses((prev) => ({ ...prev, [domainId]: { status: "error", error: String(e.message) } }));
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Competitor Overview</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Monitor competitor hotel websites and estimate their organic search performance.
        </p>
        <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
          <p>⚠️ All traffic figures are <strong>estimates</strong> derived from SERP rankings and
          keyword volumes. They are <strong>not</strong> actual analytics. Accuracy: ±7–11%.</p>
          <p className="mt-1.5 text-amber-600">
            <strong>What this means:</strong> If a competitor shows 60,000 visits/month, the real number
            is likely between 45,000 and 75,000. We calculate this by finding where their website ranks
            on Google for each keyword, then multiplying that rank's average click-through rate by the
            keyword's monthly search volume. The ±7–11% margin exists because Google search volumes
            are rounded estimates, rankings shift daily by location and device, and we track a sample
            of keywords — not every query the site ranks for.
          </p>
        </div>
      </div>

      {/* Add domain form */}
      <form onSubmit={handleAdd} className="flex gap-3 mb-8">
        <input
          type="text"
          placeholder="Add competitor domain (e.g. marriott.com)"
          value={newDomain}
          onChange={(e) => setNewDomain(e.target.value)}
          className="flex-1 px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
        <button
          type="submit"
          disabled={adding}
          className="bg-brand-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors disabled:opacity-50"
        >
          {adding ? "Adding…" : "Track Domain"}
        </button>
      </form>

      {/* Scan progress panels */}
      {Object.entries(scanStatuses).map(([domainId, scan]) => {
        if (scan.status === "idle") return null;
        const dom = domains.find((d) => d.id === domainId);
        const label = dom?.display_name || dom?.domain_name || domainId;
        const pct = scan.progress_pct ?? 0;
        const isRunning = scan.status === "running" || scan.status === "queued";

        return (
          <div key={domainId} className={`mb-3 p-4 rounded-xl border text-sm ${
            scan.status === "complete" ? "bg-green-50 border-green-200" :
            scan.status === "error"    ? "bg-red-50 border-red-200" :
                                         "bg-blue-50 border-blue-200"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-slate-800">
                {scan.status === "complete" ? "✅" : scan.status === "error" ? "❌" : "⏳"} {label} — Scan {scan.status}
              </span>
              <span className="text-xs text-slate-500">{pct}%</span>
            </div>

            {isRunning && (
              <>
                <div className="w-full bg-slate-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-brand-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(pct, 5)}%` }}
                  />
                </div>
                <div className="text-xs text-blue-700">
                  {scan.status === "queued"
                    ? "Queued — starting shortly…"
                    : `Running: ${scan.current_module_label || "initializing…"}`}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {MODULE_LABELS.map((m) => {
                    const done = scan.modules_done_labels?.includes(m);
                    const current = scan.current_module_label === m;
                    return (
                      <span key={m} className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                        done    ? "bg-green-100 text-green-700 border-green-300" :
                        current ? "bg-blue-100 text-blue-700 border-blue-300 animate-pulse" :
                                  "bg-slate-100 text-slate-400 border-slate-200"
                      }`}>
                        {done ? "✓ " : current ? "▶ " : ""}{m}
                      </span>
                    );
                  })}
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Note: SERP module takes 5–15 min due to Google rate limiting (2–5s between queries).
                </p>
              </>
            )}

            {scan.status === "complete" && (
              <p className="text-green-700 text-xs">All 6 modules complete. Dashboard updated.</p>
            )}
            {scan.status === "error" && (
              <p className="text-red-600 text-xs">Error: {scan.error}</p>
            )}
          </div>
        );
      })}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 h-64 animate-pulse">
              <div className="h-4 bg-slate-200 rounded w-3/4 mb-3" />
              <div className="h-8 bg-slate-200 rounded w-1/2 mb-4" />
              <div className="h-3 bg-slate-200 rounded w-full mb-2" />
              <div className="h-3 bg-slate-200 rounded w-5/6" />
            </div>
          ))}
        </div>
      ) : domains.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg">No competitors tracked yet.</p>
          <p className="text-sm mt-1">Add a domain above to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {domains.map((d) =>
            overviews[d.id] ? (
              <OverviewCard
                key={d.id}
                data={overviews[d.id]}
                domainId={d.id}
                onScanTrigger={handleScan}
              />
            ) : (
              <div
                key={d.id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex items-center justify-center"
              >
                <div className="text-center">
                  <p className="text-slate-600 font-medium">{d.domain_name}</p>
                  <p className="text-slate-400 text-sm mt-1">Scan not yet run</p>
                  <button
                    onClick={() => handleScan(d.id)}
                    className="mt-3 text-xs bg-brand-50 text-brand-700 border border-brand-200 rounded-lg px-3 py-1.5 hover:bg-brand-100"
                  >
                    Run First Scan
                  </button>
                </div>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
