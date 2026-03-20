import { fetchRotationProfile, fetchAdvancedTrends } from "@/lib/api";
import { RotationProfileCard } from "@/components/detail/RotationProfileCard";
import { AdvancedTrendsChart } from "@/components/detail/AdvancedTrendsChart";

export async function RotationTrendsSection({ playerId }: { playerId: string }) {
  const [rotation, advancedTrends] = await Promise.all([
    fetchRotationProfile(playerId, 20).catch(() => null),
    fetchAdvancedTrends(playerId, 20).catch(() => null),
  ]);

  if (!rotation && !advancedTrends) return null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {rotation && <RotationProfileCard rotation={rotation} />}
      {advancedTrends && advancedTrends.game_count > 0 && (
        <AdvancedTrendsChart trends={advancedTrends} />
      )}
    </div>
  );
}
