"use client";

import EstimatedBadge from "./EstimatedBadge";
import type { OverviewData } from "@/lib/api";

interface Props {
  data: OverviewData;
  domainId: string;
  onScanTrigger?: (id: string) => void;
}

const TECH_COLORS: Record<string, string> = {
  React: "bg-blue-100 text-blue-700",
  "Google Analytics": "bg-orange-100 text-orange-700",
  Cloudflare: "bg-orange-100 text-orange-700",
  WordPress: "bg-blue-100 text-blue-700",
  default: "bg-slate-100 text-slate-600",
};

function TechBadge({ name }: { name: string }) {
  const cls = TECH_COLORS[name] || TECH_COLORS.default;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {name}
    </span>
  );
}

export default function OverviewCard({ data, domainId, onScanTrigger }: Props) {
  const { traffic, tech_stack, sitemap, dom_changes, last_scan, display_name, domain } = data;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-slate-900 text-lg">
            {display_name || domain}
          </h3>
          <p className="text-slate-500 text-sm">{domain}</p>
        </div>
        {onScanTrigger && (
          <button
            onClick={() => onScanTrigger(domainId)}
            className="text-xs bg-brand-50 text-brand-700 border border-brand-200 rounded-lg px-3 py-1.5 hover:bg-brand-100 transition-colors"
          >
            Run Scan
          </button>
        )}
      </div>

      {/* Estimated traffic — big number */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
          Est. Monthly Organic Visits
        </p>
        <EstimatedBadge value={traffic.total_estimated_monthly_visits} />
        <p className="text-xs text-slate-400 mt-1">
          {traffic.keywords_tracked} keywords tracked
        </p>
      </div>

      {/* Tech stack */}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-1.5">Tech Stack</p>
        <div className="flex flex-wrap gap-1.5">
          {(tech_stack.current || []).slice(0, 6).map((t) => (
            <TechBadge key={t} name={t} />
          ))}
          {tech_stack.current.length > 6 && (
            <span className="text-xs text-slate-400">+{tech_stack.current.length - 6} more</span>
          )}
        </div>
        {tech_stack.changes_since_last_scan.added.length > 0 && (
          <p className="text-xs text-green-600 mt-1">
            {tech_stack.changes_since_last_scan.added.join(", ")}
          </p>
        )}
      </div>

      {/* Sitemap + DOM row */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-500">Pages</p>
          <p className="font-semibold text-slate-800">{sitemap.total_pages?.toLocaleString() ?? "—"}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-500">Changes</p>
          <p className="font-semibold text-slate-800">
            {dom_changes.changed_pages} / {dom_changes.monitored_pages}
          </p>
        </div>
      </div>

      {last_scan && (
        <p className="text-xs text-slate-400">
          Last scan: {new Date(last_scan).toLocaleDateString()}
        </p>
      )}
    </div>
  );
}
