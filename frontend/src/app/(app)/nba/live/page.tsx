import Link from "next/link";

import { fetchLiveGames } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function LivePage() {
  const games = await fetchLiveGames().catch(() => []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Active games
        </p>
        <h1 className="text-2xl font-bold">Live Center</h1>
      </div>

      {games.length === 0 ? (
        <Card>
          <p className="text-sm text-[color:var(--color-text-secondary)]">
            No active live games right now.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {games.map((game) => (
            <Link key={game.game_id} href={`/nba/live/${game.game_id}`}>
              <Card className="space-y-4 cursor-pointer">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
                      {game.away_team.abbreviation} @ {game.home_team.abbreviation}
                    </p>
                    <div className="mt-2 flex items-baseline gap-3">
                      <span className="font-mono text-3xl font-bold">{game.away_score}</span>
                      <span className="text-[color:var(--color-text-muted)]">-</span>
                      <span className="font-mono text-3xl font-bold">{game.home_score}</span>
                    </div>
                  </div>
                  <Badge tone="live">Q{game.period} · {game.game_clock}</Badge>
                </div>
                <div className="flex items-center justify-between text-sm text-[color:var(--color-text-secondary)]">
                  <span>{game.live_edge_count} live edges</span>
                  <span>
                    {game.updated_at
                      ? `Updated ${new Date(game.updated_at).toLocaleTimeString("en-US", {
                          hour: "numeric",
                          minute: "2-digit",
                          timeZone: "America/New_York",
                        })}`
                      : "Updated just now"}
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

