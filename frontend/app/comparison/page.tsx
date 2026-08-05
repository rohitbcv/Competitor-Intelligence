"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Domain, CompareItem } from "@/lib/api";
import TrafficComparison from "@/components/TrafficComparison";
import EstimatedBadge from "@/components/EstimatedBadge";

export default function ComparisonPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [comparison, setComparison] = useState<CompareItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const doms = await api.listDomains();
        setDomains(doms);
        if (doms.length > 0) {
          const ids = doms.slice(0, 5).map((d) => d.id);
          const cmp = await api.compare(ids);
          setComparison(cmp);
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="py-16 text-center text-slate-400">Loading comparison…</div>;
  if (error) return <div className="p-4 bg-red-50 text-red-600 rounded-lg">{error}</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Traffic Comparison</h1>
        <p className="text-slate-500 text-sm mt-1">
          Side-by-side estimated organic traffic across all tracked competitors.
        </p>
        <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
          <p>⚠️ All values are <strong>estimates</strong> — not actual analytics data. Accuracy: ±7–11%.</p>
          <p className="mt-1.5 text-amber-600">
            <strong>What this means:</strong> These numbers show estimated monthly organic visitors
            from Google Search — not total website traffic. A competitor with 60,000 estimated visits
            could realistically be anywhere between 53,000 and 67,000. Use these figures to understand
            <em> relative standing</em> (who is getting more organic search traffic than others), not
            as precise counts. Accuracy improves further as real SERP data replaces estimates.
          </p>
        </div>
      </div>

      <TrafficComparison data={comparison} />

      {/* Summary table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Domain
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Est. Monthly Visits
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Keywords Tracked
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wide">
                Technologies
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.map((item) => (
              <tr key={item.domain_id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">
                  {item.display_name || item.domain}
                </td>
                <td className="px-4 py-3">
                  <EstimatedBadge value={item.total_estimated_monthly_visits} />
                </td>
                <td className="px-4 py-3 text-slate-600">{item.keywords_tracked}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(item.technologies || []).slice(0, 3).map((t) => (
                      <span key={t} className="text-xs bg-slate-100 text-slate-600 rounded-full px-2 py-0.5">
                        {t}
                      </span>
                    ))}
                    {item.technologies?.length > 3 && (
                      <span className="text-xs text-slate-400">+{item.technologies.length - 3}</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
