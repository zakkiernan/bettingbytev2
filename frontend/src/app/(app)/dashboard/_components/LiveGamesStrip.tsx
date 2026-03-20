import Link from "next/link";
import { fetchLiveGames } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export default async function LiveGamesStrip() {
  const liveGames = await fetchLiveGames().catch(() => []);

  if (liveGames.length === 0) {
    return null;
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-1">
      {liveGames.map((game) => (
        <Link key={game.game_id} href={`/nba/live/${game.game_id}`} className="flex-shrink-0">
          <Card className="w-[260px] cursor-pointer">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-[color:var(--color-text-muted)]">
                  {game.away_team.abbreviation} @ {game.home_team.abbreviation}
                </p>
                <div className="mt-1.5 flex items-baseline gap-2">
                  <span className="font-mono text-2xl font-bold">{game.away_score}</span>
                  <span className="text-[color:var(--color-text-muted)]">-</span>
                  <span className="font-mono text-2xl font-bold">{game.home_score}</span>
                </div>
              </div>
              <Badge tone="live" className="gap-1.5">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--color-accent)] opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[color:var(--color-accent)]" />
                </span>
                Q{game.period} {game.game_clock}
              </Badge>
            </div>
            {game.live_edge_count > 0 && (
              <div className="mt-3 text-xs text-[color:var(--color-text-muted)]">
                <span className="font-mono font-semibold text-[color:var(--color-accent)]">
                  {game.live_edge_count}
                </span>{" "}
                live {game.live_edge_count === 1 ? "edge" : "edges"}
              </div>
            )}
          </Card>
        </Link>
      ))}
    </div>
  );
}
