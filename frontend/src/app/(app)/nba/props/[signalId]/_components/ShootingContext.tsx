import { Card } from "@/components/ui/card";
import { ZoneHeatmap } from "@/components/charts/ZoneHeatmap";
import { PlayTypeBreakdown } from "@/components/stats/PlayTypeBreakdown";
import { fetchPlayerShotLocations, fetchPlayerPlayTypes } from "@/lib/nba-api";

interface ShootingContextProps {
  playerId: string;
  statType: string;
}

export async function ShootingContext({ playerId, statType }: ShootingContextProps) {
  // Only show for scoring-related props
  if (!["points", "threes", "three_pointers_made"].includes(statType)) {
    return null;
  }

  const [locations, playTypes] = await Promise.all([
    fetchPlayerShotLocations(playerId).catch(() => null),
    fetchPlayerPlayTypes(playerId).catch(() => null),
  ]);

  const hasLocations = (locations?.zones.length ?? 0) > 0;
  const hasPlayTypes = (playTypes?.offensive.length ?? 0) > 0;

  if (!hasLocations && !hasPlayTypes) return null;

  // Find the top play type for a quick narrative
  const topPlayType = playTypes?.offensive
    .sort((a, b) => (b.poss_pct ?? 0) - (a.poss_pct ?? 0))[0];

  return (
    <div className="space-y-6">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Scoring profile
      </p>

      {topPlayType && topPlayType.poss_pct != null && (
        <div className="rounded-xl border border-[color:var(--color-accent)]/20 bg-[color:var(--color-accent)]/5 px-4 py-3">
          <p className="text-sm text-[color:var(--color-text-secondary)]">
            <span className="font-semibold text-[color:var(--color-text-primary)]">
              {(topPlayType.poss_pct * 100).toFixed(0)}%
            </span>{" "}
            of possessions are{" "}
            <span className="font-semibold text-[color:var(--color-text-primary)]">{topPlayType.play_type}</span>
            {topPlayType.percentile != null && (
              <span>
                {" "}({Math.round(topPlayType.percentile)}th percentile PPP)
              </span>
            )}
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {hasLocations && (
          <Card className="p-4">
            <ZoneHeatmap zones={locations!.zones} />
          </Card>
        )}
        {hasPlayTypes && (
          <Card className="p-4">
            <PlayTypeBreakdown entries={playTypes!.offensive.slice(0, 6)} />
          </Card>
        )}
      </div>
    </div>
  );
}
