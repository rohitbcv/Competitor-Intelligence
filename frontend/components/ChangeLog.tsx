"use client";

import type { ChangeEvent } from "@/lib/api";

interface ChangeLogEntry {
  domain: string;
  type: "dom" | "tech" | "sitemap";
  description: string;
  timestamp: string;
}

interface Props {
  entries: ChangeLogEntry[];
}

const TYPE_CONFIG = {
  dom: { label: "Page Changed", color: "bg-amber-100 text-amber-700 border-amber-300" },
  tech: { label: "Tech Update", color: "bg-blue-100 text-blue-700 border-blue-300" },
  sitemap: { label: "Sitemap Growth", color: "bg-green-100 text-green-700 border-green-300" },
};

export default function ChangeLog({ entries }: Props) {
  const sorted = [...entries].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <h2 className="font-semibold text-slate-900 text-lg mb-4">Change Log</h2>

      {sorted.length === 0 ? (
        <p className="text-slate-400 text-sm">No changes detected yet.</p>
      ) : (
        <div className="space-y-3">
          {sorted.map((entry, i) => {
            const cfg = TYPE_CONFIG[entry.type];
            return (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition-colors"
              >
                <div className="mt-0.5 flex-shrink-0 w-2 h-2 rounded-full bg-brand-400 mt-2" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-slate-800 text-sm">{entry.domain}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cfg.color}`}
                    >
                      {cfg.label}
                    </span>
                  </div>
                  <p className="text-slate-600 text-sm mt-0.5">{entry.description}</p>
                </div>
                <time className="text-xs text-slate-400 whitespace-nowrap flex-shrink-0">
                  {new Date(entry.timestamp).toLocaleDateString()}
                </time>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
