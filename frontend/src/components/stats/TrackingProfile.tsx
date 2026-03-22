import type { TrackingMeasure } from "@/types/api";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function StatRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-[color:var(--color-text-muted)]">{label}</span>
      <div className="text-right">
        <span className="font-mono text-sm font-semibold">{value}</span>
        {sub && <span className="ml-1.5 text-xs text-[color:var(--color-text-muted)]">{sub}</span>}
      </div>
    </div>
  );
}

function MeasureCard({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("space-y-1 p-4", className)}>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--color-accent)]">{title}</p>
      {children}
    </Card>
  );
}

interface TrackingProfileProps {
  measures: TrackingMeasure[];
  className?: string;
}

export function TrackingProfile({ measures, className }: TrackingProfileProps) {
  const catchShoot = measures.find((m) => m.measure_type === "CatchShoot");
  const pullUp = measures.find((m) => m.measure_type === "PullUpShot");
  const drives = measures.find((m) => m.measure_type === "Drives");

  if (!catchShoot && !pullUp && !drives) {
    return (
      <div className={cn("py-8 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No tracking data available
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Shooting & drive profile
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {catchShoot && (
          <MeasureCard title="Catch & Shoot">
            <StatRow label="FG" value={`${fmt(catchShoot.fgm, 1)}/${fmt(catchShoot.fga, 1)}`} />
            <StatRow label="FG%" value={pct(catchShoot.fg_pct)} />
            <StatRow label="3P%" value={pct(catchShoot.fg3_pct)} />
            <StatRow label="eFG%" value={pct(catchShoot.efg_pct)} />
            <StatRow label="Points" value={fmt(catchShoot.pts)} />
          </MeasureCard>
        )}
        {pullUp && (
          <MeasureCard title="Pull-Up">
            <StatRow label="FG" value={`${fmt(pullUp.fgm, 1)}/${fmt(pullUp.fga, 1)}`} />
            <StatRow label="FG%" value={pct(pullUp.fg_pct)} />
            <StatRow label="3P%" value={pct(pullUp.fg3_pct)} />
            <StatRow label="eFG%" value={pct(pullUp.efg_pct)} />
            <StatRow label="Points" value={fmt(pullUp.pts)} />
          </MeasureCard>
        )}
        {drives && (
          <MeasureCard title="Drives">
            <StatRow label="Drives/gm" value={fmt(drives.drives)} />
            <StatRow label="Drive FG%" value={pct(drives.drive_fg_pct)} />
            <StatRow label="Drive FT%" value={pct(drives.drive_ft_pct)} />
            <StatRow label="Drive PTS" value={fmt(drives.drive_pts)} />
            <StatRow label="Drive AST" value={fmt(drives.drive_ast)} />
            <StatRow label="Drive TOV" value={fmt(drives.drive_tov)} />
          </MeasureCard>
        )}
      </div>
    </div>
  );
}
