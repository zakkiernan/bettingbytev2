import { Card } from "@/components/ui/card";
import { PlayTypeBreakdown } from "@/components/stats/PlayTypeBreakdown";
import { TrackingProfile } from "@/components/stats/TrackingProfile";
import { HustleCard } from "@/components/stats/HustleCard";
import { DefenseZones } from "@/components/stats/DefenseZones";
import { OnOffTable } from "@/components/stats/OnOffTable";
import { ClutchBadge } from "@/components/stats/ClutchBadge";
import {
  fetchPlayerPlayTypes,
  fetchPlayerTracking,
  fetchPlayerHustle,
  fetchPlayerDefense,
  fetchPlayerOnOff,
  fetchPlayerClutch,
  fetchPlayerProfile,
} from "@/lib/nba-api";

export async function AdvancedStatsSection({ playerId }: { playerId: string }) {
  const [playTypes, tracking, hustle, defense, onOff, clutch, profile] = await Promise.all([
    fetchPlayerPlayTypes(playerId).catch(() => null),
    fetchPlayerTracking(playerId).catch(() => null),
    fetchPlayerHustle(playerId).catch(() => null),
    fetchPlayerDefense(playerId).catch(() => null),
    fetchPlayerOnOff(playerId).catch(() => null),
    fetchPlayerClutch(playerId).catch(() => null),
    fetchPlayerProfile(playerId).catch(() => null),
  ]);

  const hasAny =
    (playTypes?.offensive.length ?? 0) > 0 ||
    (tracking?.measures.length ?? 0) > 0 ||
    hustle?.season_totals ||
    (defense?.zones.length ?? 0) > 0 ||
    (onOff?.splits.length ?? 0) > 0 ||
    (clutch?.entries.length ?? 0) > 0;

  if (!hasAny) return null;

  return (
    <div className="space-y-6">
      {playTypes && playTypes.offensive.length > 0 && (
        <Card>
          <PlayTypeBreakdown entries={playTypes.offensive} />
        </Card>
      )}

      {tracking && tracking.measures.length > 0 && (
        <TrackingProfile measures={tracking.measures} />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {hustle?.season_totals && (
          <Card>
            <HustleCard stats={hustle.season_totals} />
          </Card>
        )}

        {clutch && clutch.entries.length > 0 && (
          <Card>
            <ClutchBadge
              entries={clutch.entries}
              seasonFgPct={profile?.season_averages.fg_pct}
            />
          </Card>
        )}
      </div>

      {defense && defense.zones.length > 0 && (
        <Card>
          <DefenseZones zones={defense.zones} />
        </Card>
      )}

      {onOff && onOff.splits.length > 0 && (
        <Card>
          <OnOffTable splits={onOff.splits} />
        </Card>
      )}
    </div>
  );
}
