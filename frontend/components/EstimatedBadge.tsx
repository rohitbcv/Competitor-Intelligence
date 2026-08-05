"use client";

/**
 * EstimatedBadge — wraps any traffic number with a visible "Estimated" label.
 * Required by product: every traffic number must have this indicator.
 */
export default function EstimatedBadge({ value }: { value: number }) {
  return (
    <span
      className="inline-flex items-center gap-1 group relative"
      title="This is an estimate based on search rankings and is not actual analytics data. Accuracy range: +/- 7–11%."
    >
      <span className="font-bold text-2xl text-slate-800">
        ~{value.toLocaleString()}
      </span>
      <span className="text-xs bg-amber-100 text-amber-700 border border-amber-300 rounded px-1.5 py-0.5 font-medium">
        est.
      </span>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 w-64 text-xs bg-slate-800 text-white rounded p-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
        This is an estimate based on search rankings and is not actual analytics data.
        Accuracy range: ±7–11%.
      </span>
    </span>
  );
}
