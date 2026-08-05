"use client";

import { useState } from "react";
import type { KeywordEstimate } from "@/lib/api";

interface Props {
  keywords: KeywordEstimate[];
  domain: string;
  brandedPct?: number; // % of clicks from branded queries
}

type SortKey = keyof Pick<
  KeywordEstimate,
  "keyword" | "monthly_volume" | "serp_rank" | "ctr" | "estimated_visits" | "delta_pct"
>;

function exportCSV(keywords: KeywordEstimate[], domain: string) {
  const headers = ["Query", "Clicks (est.)", "Impressions", "CTR", "Avg Position", "Delta %"];
  const rows = keywords.map((k) => [
    k.keyword,
    k.estimated_visits,
    k.monthly_volume,
    `${(k.ctr * 100).toFixed(2)}%`,
    k.serp_rank ?? "—",
    k.delta_pct !== 0 ? `${k.delta_pct > 0 ? "+" : ""}${k.delta_pct}%` : "0%",
  ]);
  const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${domain}_keywords.csv`;
  a.click();
}

function DeltaBadge({ pct, visits }: { pct: number; visits: number }) {
  if (pct === 0 || visits === 0)
    return <span className="text-slate-400 text-xs">0%</span>;
  const positive = pct > 0;
  return (
    <span
      className={`text-xs font-semibold ${
        positive ? "text-green-600" : "text-red-500"
      }`}
    >
      {positive ? "+" : ""}
      {pct}%
    </span>
  );
}

function RankBadge({ rank }: { rank: number | null }) {
  if (!rank) return <span className="text-slate-400 text-xs">—</span>;
  const color =
    rank <= 3
      ? "bg-green-100 text-green-700"
      : rank <= 10
      ? "bg-amber-100 text-amber-700"
      : "bg-slate-100 text-slate-500";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {rank}
    </span>
  );
}

function formatK(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

const COLUMNS: { key: SortKey; label: string; tooltip: string }[] = [
  { key: "keyword",          label: "Query",        tooltip: "Search query / keyword" },
  { key: "estimated_visits", label: "Clicks ▾",     tooltip: "Estimated monthly organic clicks" },
  { key: "monthly_volume",   label: "Impressions",  tooltip: "Monthly search volume (times query is searched)" },
  { key: "ctr",              label: "CTR",          tooltip: "Estimated click-through rate at this rank position" },
  { key: "serp_rank",        label: "Avg Position", tooltip: "Estimated average SERP rank (lower = better)" },
  { key: "delta_pct",        label: "Delta (Clicks)", tooltip: "Change in estimated clicks vs. previous scan" },
];

export default function KeywordTable({ keywords, domain, brandedPct }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("estimated_visits");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "ranked" | "unranked">("all");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "serp_rank" ? "asc" : "desc");
    }
  };

  const filtered = keywords
    .filter((k) => {
      const matchSearch = k.keyword.toLowerCase().includes(search.toLowerCase());
      const matchFilter =
        filter === "all" ||
        (filter === "ranked" && k.serp_rank != null) ||
        (filter === "unranked" && k.serp_rank == null);
      return matchSearch && matchFilter;
    })
    .sort((a, b) => {
      // For rank: null = worst (push to bottom regardless of sort direction)
      if (sortKey === "serp_rank") {
        if (a.serp_rank == null && b.serp_rank == null) return 0;
        if (a.serp_rank == null) return 1;
        if (b.serp_rank == null) return -1;
        return sortDir === "asc"
          ? a.serp_rank - b.serp_rank
          : b.serp_rank - a.serp_rank;
      }
      const av = (a[sortKey] as number) ?? -Infinity;
      const bv = (b[sortKey] as number) ?? -Infinity;
      return sortDir === "asc" ? av - bv : bv - av;
    });

  const ranked = keywords.filter((k) => k.serp_rank != null).length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-slate-100">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-slate-900 text-lg">Top Queries</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Queries driving visibility and clicks from search engines.
            </p>
            {brandedPct != null && (
              <p className="text-xs text-slate-400 mt-0.5">
                Branded queries account for{" "}
                <span className="font-medium text-slate-600">{brandedPct}%</span> of clicks.
              </p>
            )}
          </div>
          <button
            onClick={() => exportCSV(filtered, domain)}
            className="shrink-0 text-sm bg-slate-50 text-slate-600 border border-slate-200 rounded-lg px-4 py-2 hover:bg-slate-100 transition-colors"
          >
            Export CSV
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <input
            type="text"
            placeholder="Filter queries..."
            className="flex-1 min-w-[180px] px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs font-medium">
            {(["all", "ranked", "unranked"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-2 capitalize transition-colors ${
                  filter === f
                    ? "bg-brand-600 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {f === "all" ? `All (${keywords.length})` : f === "ranked" ? `Ranked (${ranked})` : `Unranked (${keywords.length - ranked})`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100">
              {COLUMNS.map(({ key, label, tooltip }) => (
                <th
                  key={key}
                  title={tooltip}
                  onClick={() => handleSort(key)}
                  className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide cursor-pointer hover:text-brand-600 select-none whitespace-nowrap"
                >
                  {label}
                  {sortKey === key && (
                    <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((k, i) => (
              <tr
                key={k.keyword + i}
                className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
              >
                {/* Query */}
                <td className="px-4 py-3 text-slate-800 font-medium max-w-[260px] truncate">
                  {k.keyword}
                </td>

                {/* Clicks */}
                <td className="px-4 py-3 font-semibold text-slate-800">
                  {k.estimated_visits > 0 ? k.estimated_visits.toLocaleString() : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>

                {/* Impressions */}
                <td className="px-4 py-3 text-slate-600">
                  {formatK(k.monthly_volume)}
                </td>

                {/* CTR */}
                <td className="px-4 py-3 text-slate-600">
                  {k.ctr > 0 ? `${(k.ctr * 100).toFixed(2)}%` : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>

                {/* Avg Position */}
                <td className="px-4 py-3">
                  <RankBadge rank={k.serp_rank} />
                </td>

                {/* Delta */}
                <td className="px-4 py-3">
                  <DeltaBadge pct={k.delta_pct} visits={k.estimated_visits} />
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-10 text-slate-400">
                  No keywords match your filter
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
        <span>
          Showing {filtered.length} of {keywords.length} queries
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
          All Clicks &amp; CTR are estimates (±7–11%)
        </span>
      </div>
    </div>
  );
}
