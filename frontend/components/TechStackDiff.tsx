"use client";

import type { TechHistoryItem } from "@/lib/api";

interface Props {
  histories: { domain: string; items: TechHistoryItem[] }[];
}

function TechBadge({ name, state }: { name: string; state?: "added" | "removed" | "current" }) {
  const cls =
    state === "added"
      ? "bg-green-100 text-green-700 border border-green-300"
      : state === "removed"
      ? "bg-red-100 text-red-600 border border-red-200 line-through opacity-70"
      : "bg-slate-100 text-slate-700 border border-slate-200";

  return (
    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${cls}`}>{name}</span>
  );
}

export default function TechStackDiff({ histories }: Props) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <h2 className="font-semibold text-slate-900 text-lg mb-4">Tech Stack Comparison</h2>

      <div
        className="grid gap-6"
        style={{ gridTemplateColumns: `repeat(${Math.min(histories.length, 3)}, 1fr)` }}
      >
        {histories.map(({ domain, items }) => {
          const latest = items[0];
          return (
            <div key={domain} className="border border-slate-200 rounded-lg p-4">
              <h3 className="font-semibold text-slate-800 text-sm mb-3">{domain}</h3>

              {latest ? (
                <>
                  <div className="mb-3">
                    <p className="text-xs text-slate-500 mb-2">Current Stack</p>
                    <div className="flex flex-wrap gap-1.5">
                      {latest.technologies.map((t) => (
                        <TechBadge key={t} name={t} state="current" />
                      ))}
                    </div>
                  </div>

                  {latest.added.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs text-green-600 font-semibold mb-1">+ Added</p>
                      <div className="flex flex-wrap gap-1.5">
                        {latest.added.map((t) => (
                          <TechBadge key={t} name={t} state="added" />
                        ))}
                      </div>
                    </div>
                  )}

                  {latest.removed.length > 0 && (
                    <div>
                      <p className="text-xs text-red-500 font-semibold mb-1">− Removed</p>
                      <div className="flex flex-wrap gap-1.5">
                        {latest.removed.map((t) => (
                          <TechBadge key={t} name={t} state="removed" />
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-slate-400 mt-3">
                    Scanned: {new Date(latest.scraped_at).toLocaleDateString()}
                  </p>
                </>
              ) : (
                <p className="text-slate-400 text-sm">No data yet</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
