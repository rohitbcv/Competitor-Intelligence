"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { CompareItem } from "@/lib/api";

interface Props {
  data: CompareItem[];
}

const COLORS = ["#0ea5e9", "#f59e0b", "#10b981", "#6366f1", "#ef4444"];

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-lg text-sm">
      <p className="font-semibold text-slate-800 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.fill }}>
          ~{Number(p.value).toLocaleString()} <span className="text-slate-400 text-xs">(est.)</span>
        </p>
      ))}
      <p className="text-xs text-slate-400 mt-1 border-t pt-1">
        Estimated organic visits · ±7–11% variance
      </p>
    </div>
  );
}

export default function TrafficComparison({ data }: Props) {
  const chartData = data.map((d, i) => ({
    name: d.display_name || d.domain,
    visits: d.total_estimated_monthly_visits,
    fill: COLORS[i % COLORS.length],
  }));

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-slate-900 text-lg">
            Estimated Traffic Comparison
          </h2>
          <p className="text-xs text-amber-600 mt-0.5">
            ⚠️ All values are estimates — not actual analytics data
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 12, fill: "#64748b" }}
            angle={-30}
            textAnchor="end"
            interval={0}
          />
          <YAxis
            label={{
              value: "Estimated Monthly Organic Visits",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 11, fill: "#94a3b8" },
              offset: -5,
            }}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="visits" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
