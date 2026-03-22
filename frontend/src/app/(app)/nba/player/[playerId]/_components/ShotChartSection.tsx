import { Card } from "@/components/ui/card";
import { ShotChart } from "@/components/charts/ShotChart";
import { ZoneHeatmap } from "@/components/charts/ZoneHeatmap";
import { fetchPlayerShotChart, fetchPlayerShotLocations } from "@/lib/nba-api";

export async function ShotChartSection({ playerId }: { playerId: string }) {
  const [chartData, locationData] = await Promise.all([
    fetchPlayerShotChart(playerId).catch(() => null),
    fetchPlayerShotLocations(playerId).catch(() => null),
  ]);

  if (!chartData?.shots.length && !locationData?.zones.length) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
      {chartData && chartData.shots.length > 0 && (
        <Card>
          <ShotChart
            shots={chartData.shots}
            title={`Shot chart \u00b7 ${chartData.total_shots} shots \u00b7 ${(chartData.field_goal_pct * 100).toFixed(1)}% FG`}
          />
        </Card>
      )}
      {locationData && locationData.zones.length > 0 && (
        <Card>
          <ZoneHeatmap zones={locationData.zones} />
        </Card>
      )}
    </div>
  );
}
