import type { OnOffSplit } from "@/types/api";
import { cn } from "@/lib/utils";

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

function diffCell(on: number | null | undefined, off: number | null | undefined, inverse = false) {
  if (on == null || off == null) return <td className="py-1.5 text-right font-mono text-sm">--</td>;
  const diff = on - off;
  // For most stats, positive diff = good when ON court
  // For def_rating and tov_pct, lower is better (inverse)
  const isGood = inverse ? diff < 0 : diff > 0;
  const color = Math.abs(diff) < 0.5
    ? ""
    : isGood
      ? "text-[color:var(--color-positive)]"
      : "text-[color:var(--color-negative)]";
  return (
    <td className={cn("py-1.5 text-right font-mono text-sm font-semibold", color)}>
      {diff > 0 ? "+" : ""}{diff.toFixed(1)}
    </td>
  );
}

interface OnOffTableProps {
  splits: OnOffSplit[];
  className?: string;
}

const ROWS: { label: string; key: keyof OnOffSplit; inverse?: boolean }[] = [
  { label: "Off Rating", key: "off_rating" },
  { label: "Def Rating", key: "def_rating", inverse: true },
  { label: "Net Rating", key: "net_rating" },
  { label: "Pace", key: "pace" },
  { label: "TS%", key: "ts_pct" },
  { label: "eFG%", key: "efg_pct" },
  { label: "AST%", key: "ast_pct" },
  { label: "TOV%", key: "tov_pct", inverse: true },
  { label: "REB%", key: "reb_pct" },
  { label: "PIE", key: "pie" },
  { label: "+/-", key: "plus_minus" },
];

export function OnOffTable({ splits, className }: OnOffTableProps) {
  const on = splits.find((s) => s.court_status === "on");
  const off = splits.find((s) => s.court_status === "off");

  if (!on && !off) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No on/off court data available
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        On/off court impact
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-xs text-[color:var(--color-text-muted)]">
              <th className="pb-2 text-left font-medium">Stat</th>
              <th className="pb-2 text-right font-medium">On Court</th>
              <th className="pb-2 text-right font-medium">Off Court</th>
              <th className="pb-2 text-right font-medium">Diff</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]/50">
            {ROWS.map(({ label, key, inverse }) => (
              <tr key={key}>
                <td className="py-1.5 text-xs font-medium text-[color:var(--color-text-secondary)]">{label}</td>
                <td className="py-1.5 text-right font-mono text-sm">{fmt(on?.[key] as number | null | undefined)}</td>
                <td className="py-1.5 text-right font-mono text-sm">{fmt(off?.[key] as number | null | undefined)}</td>
                {diffCell(on?.[key] as number | null | undefined, off?.[key] as number | null | undefined, inverse)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {on?.gp && (
        <p className="text-xs text-[color:var(--color-text-muted)]">
          Based on {on.gp} games played
        </p>
      )}
    </div>
  );
}
