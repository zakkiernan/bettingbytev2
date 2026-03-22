import type { HustleStatsSeason } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function perGame(total: number | null | undefined, gp: number | null | undefined): string {
  if (total == null || !gp) return "--";
  return (total / gp).toFixed(1);
}

function HustleStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="font-mono text-lg font-bold">{value}</span>
      <span className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">{label}</span>
    </div>
  );
}

interface HustleCardProps {
  stats: HustleStatsSeason | null | undefined;
  className?: string;
}

export function HustleCard({ stats, className }: HustleCardProps) {
  if (!stats || !stats.games_played) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No hustle data available
      </div>
    );
  }

  const gp = stats.games_played;
  const deflPg = (stats.deflections ?? 0) / gp;
  const contestedPg = (stats.contested_shots ?? 0) / gp;
  const isHighMotor = deflPg >= 3 && contestedPg >= 8;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Hustle stats
        </p>
        {isHighMotor && <Badge tone="success">High Motor</Badge>}
      </div>
      <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
        <HustleStat label="Deflections" value={perGame(stats.deflections, gp)} />
        <HustleStat label="Contested" value={perGame(stats.contested_shots, gp)} />
        <HustleStat label="Charges" value={perGame(stats.charges_drawn, gp)} />
        <HustleStat label="Screen AST" value={perGame(stats.screen_assists, gp)} />
        <HustleStat label="Loose Balls" value={perGame(stats.loose_balls_recovered, gp)} />
        <HustleStat label="Box Outs" value={perGame(stats.box_outs, gp)} />
      </div>
      <p className="text-xs text-[color:var(--color-text-muted)]">
        Per game averages over {gp} games
      </p>
    </div>
  );
}
