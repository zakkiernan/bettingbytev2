import { fetchPlayerTrends } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export async function TrendSection({ playerId }: { playerId: string }) {
  const trends = await fetchPlayerTrends(playerId, "points", 10).catch(() => []);

  const avgTrend = trends.length
    ? trends.reduce((sum, point) => sum + point.value, 0) / trends.length
    : 0;
  const hitRate = trends.filter((point) => point.hit).length;

  return (
    <Card>
      <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Recent points trend</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat title="Last 10 avg" value={avgTrend.toFixed(1)} />
        <Stat title="Line hit rate" value={`${hitRate}/${trends.length}`} />
      </div>
      <div className="mt-4 space-y-2">
        {trends.map((point, idx) => (
          <div key={`${point.game_date}-${idx}`} className="flex items-center justify-between rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-3 py-2 text-sm">
            <span className="text-[color:var(--color-text-secondary)]">
              {point.game_date
                ? new Date(point.game_date).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    timeZone: "America/New_York",
                  })
                : "\u2014"}
            </span>
            <span className="font-mono">{point.value.toFixed(1)}</span>
            <span className="font-mono text-[color:var(--color-text-muted)]">line {point.line?.toFixed(1) ?? "\u2014"}</span>
            <Badge tone={point.hit ? "success" : "default"}>{point.hit == null ? "n/a" : point.hit ? "hit" : "miss"}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Stat({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 text-center">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{title}</div>
      <div className="mt-1 font-mono text-2xl font-bold">{value}</div>
    </div>
  );
}
