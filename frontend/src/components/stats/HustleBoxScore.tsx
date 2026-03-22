import type { GameHustleRow } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function fmt(v: number | null | undefined, decimals = 0): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

function hustleScore(r: GameHustleRow): number {
  return (
    (r.deflections ?? 0) * 1.5 +
    (r.contested_shots ?? 0) * 1.0 +
    (r.charges_drawn ?? 0) * 2.0 +
    (r.screen_assists ?? 0) * 1.0 +
    (r.loose_balls_recovered ?? 0) * 1.5 +
    (r.box_outs ?? 0) * 0.5
  );
}

interface HustleBoxScoreProps {
  players: GameHustleRow[];
  className?: string;
}

export function HustleBoxScore({ players, className }: HustleBoxScoreProps) {
  if (players.length === 0) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No hustle data available
      </div>
    );
  }

  const sorted = [...players].sort((a, b) => hustleScore(b) - hustleScore(a));
  const mvpId = sorted[0]?.player_id;

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Hustle box score
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-xs text-[color:var(--color-text-muted)]">
              <th className="pb-2 text-left font-medium">Player</th>
              <th className="pb-2 text-right font-medium">MIN</th>
              <th className="pb-2 text-right font-medium">DEFL</th>
              <th className="pb-2 text-right font-medium">CONT</th>
              <th className="pb-2 text-right font-medium">CHG</th>
              <th className="pb-2 text-right font-medium">SCR</th>
              <th className="pb-2 text-right font-medium">LB</th>
              <th className="pb-2 text-right font-medium">BO</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]/50">
            {sorted.map((p) => (
              <tr key={p.player_id} className="text-[color:var(--color-text-secondary)]">
                <td className="py-2">
                  <span className="flex items-center gap-1.5 font-medium text-[color:var(--color-text-primary)]">
                    {p.player_name}
                    {p.player_id === mvpId && <Badge tone="success" className="scale-75">Hustle MVP</Badge>}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">{fmt(p.minutes, 1)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.deflections)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.contested_shots)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.charges_drawn)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.screen_assists)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.loose_balls_recovered)}</td>
                <td className="py-2 text-right font-mono">{fmt(p.box_outs)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
