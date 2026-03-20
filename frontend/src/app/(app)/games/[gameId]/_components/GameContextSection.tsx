import { fetchGameContext } from "@/lib/api";
import { LineupComparison } from "@/components/detail/LineupComparison";
import { TeamDefenseComparison } from "@/components/detail/TeamDefenseComparison";

export async function GameContextSection({ gameId }: { gameId: string }) {
  const context = await fetchGameContext(gameId).catch(() => null);

  if (!context) return null;

  return (
    <>
      <div>
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Lineup & injuries
        </p>
        <LineupComparison home={context.home_team} away={context.away_team} />
      </div>

      <TeamDefenseComparison home={context.home_team} away={context.away_team} />
    </>
  );
}
