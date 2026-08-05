"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Domain, ChangesData, TechHistoryItem } from "@/lib/api";
import ChangeLog from "@/components/ChangeLog";

export default function ChangesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entries, setEntries] = useState<
    { domain: string; type: "dom" | "tech" | "sitemap"; description: string; timestamp: string }[]
  >([]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const doms = await api.listDomains();
        const allEntries: typeof entries = [];

        await Promise.allSettled(
          doms.map(async (d) => {
            const domLabel = d.display_name || d.domain_name;

            // DOM changes
            try {
              const changes = await api.getChanges(d.id);
              changes.events
                .filter((e) => e.has_changed)
                .forEach((e) => {
                  allEntries.push({
                    domain: domLabel,
                    type: "dom",
                    description: `Page content changed: ${e.page_url}`,
                    timestamp: e.checked_at,
                  });
                });
            } catch {}

            // Tech changes
            try {
              const techHistory = await api.getTechHistory(d.id);
              techHistory.forEach((item) => {
                if (item.added.length > 0) {
                  allEntries.push({
                    domain: domLabel,
                    type: "tech",
                    description: `New technology detected: ${item.added.join(", ")}`,
                    timestamp: item.scraped_at,
                  });
                }
                if (item.removed.length > 0) {
                  allEntries.push({
                    domain: domLabel,
                    type: "tech",
                    description: `Technology removed: ${item.removed.join(", ")}`,
                    timestamp: item.scraped_at,
                  });
                }
              });
            } catch {}

            // Sitemap growth
            try {
              const sitemap = await api.getSitemap(d.id);
              if (sitemap.page_growth_4w > 0) {
                allEntries.push({
                  domain: domLabel,
                  type: "sitemap",
                  description: `+${sitemap.page_growth_4w} new pages detected (${sitemap.total_pages.toLocaleString()} total)`,
                  timestamp: sitemap.scanned_at,
                });
              }
            } catch {}
          })
        );

        setEntries(allEntries);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="py-16 text-center text-slate-400">Loading change log…</div>;
  if (error) return <div className="p-4 bg-red-50 text-red-600 rounded-lg">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Change Log</h1>
        <p className="text-slate-500 text-sm mt-1">
          Timeline of DOM changes, tech updates, and sitemap growth across all competitors.
        </p>
      </div>

      <div className="flex gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-amber-400 inline-block" />
          <span className="text-slate-600">Page Changes</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-blue-400 inline-block" />
          <span className="text-slate-600">Tech Updates</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-green-400 inline-block" />
          <span className="text-slate-600">Sitemap Growth</span>
        </div>
      </div>

      <ChangeLog entries={entries} />
    </div>
  );
}
