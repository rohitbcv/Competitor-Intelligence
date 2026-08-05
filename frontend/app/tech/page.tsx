"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Domain, TechHistoryItem } from "@/lib/api";
import TechStackDiff from "@/components/TechStackDiff";

export default function TechPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [histories, setHistories] = useState<{ domain: string; items: TechHistoryItem[] }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const doms = await api.listDomains();
        setDomains(doms);
        const results = await Promise.allSettled(
          doms.slice(0, 3).map((d) => api.getTechHistory(d.id))
        );
        const hist = results.map((r, i) => ({
          domain: doms[i].display_name || doms[i].domain_name,
          items: r.status === "fulfilled" ? r.value : [],
        }));
        setHistories(hist);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="py-16 text-center text-slate-400">Loading tech stacks…</div>;
  if (error) return <div className="p-4 bg-red-50 text-red-600 rounded-lg">{error}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Tech Stack Diff</h1>
        <p className="text-slate-500 text-sm mt-1">
          Compare technologies used by competitors and track changes over time.
        </p>
      </div>

      <TechStackDiff histories={histories} />

      {/* Full history table */}
      {histories.map(({ domain, items }) =>
        items.length > 1 ? (
          <div key={domain} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="font-semibold text-slate-800 mb-3">{domain} — Scan History</h3>
            <div className="space-y-3">
              {items.slice(0, 5).map((item, i) => (
                <div key={i} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                  <div className="flex items-center gap-2 mb-1">
                    <time className="text-xs text-slate-500">
                      {new Date(item.scraped_at).toLocaleDateString()}
                    </time>
                    {item.added.length > 0 && (
                      <span className="text-xs text-green-600">
                        +{item.added.length} added
                      </span>
                    )}
                    {item.removed.length > 0 && (
                      <span className="text-xs text-red-500">
                        −{item.removed.length} removed
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {item.added.map((t) => (
                      <span key={t} className="text-xs bg-green-100 text-green-700 rounded-full px-2 py-0.5">
                        + {t}
                      </span>
                    ))}
                    {item.removed.map((t) => (
                      <span key={t} className="text-xs bg-red-100 text-red-600 rounded-full px-2 py-0.5 line-through">
                        − {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null
      )}
    </div>
  );
}
