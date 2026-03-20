import Link from "next/link";
import { fetchGamesToday } from "@/lib/api";
import { Card } from "@/components/ui/card";

export default async function GamesGrid() {
  const games = await fetchGamesToday().catch(() => []);

  if (games.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--color-border)] py-20 text-center">
        <p className="text-[color:var(--color-text-secondary)]">No games scheduled for tonight.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {games.map((g) => {
        const time = g.game_time_utc
          ? new Date(g.game_time_utc).toLocaleTimeString("en-US", {
              hour: "numeric",
              minute: "2-digit",
              timeZone: "America/New_York",
            })
          : null;

        return (
          <Link key={g.game_id} href={`/nba/games/${g.game_id}`}>
            <Card className="transition-colors hover:border-[color:var(--color-border)] hover:bg-[color:var(--color-surface-elevated)]/80">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-lg font-bold">
                    {g.away_team.abbreviation}{" "}
                    <span className="text-[color:var(--color-text-muted)]">@</span>{" "}
                    {g.home_team.abbreviation}
                  </div>
                  <div className="text-sm text-[color:var(--color-text-secondary)]">
                    {g.away_team.full_name} vs {g.home_team.full_name}
                  </div>
                </div>
                <div className="text-right">
                  {time && (
                    <div className="font-mono text-sm text-[color:var(--color-text-secondary)]">{time}</div>
                  )}
                </div>
              </div>

              <div className="mt-3 flex gap-3 text-xs text-[color:var(--color-text-muted)]">
                <span>
                  <span className="font-mono font-semibold text-[color:var(--color-text-secondary)]">{g.prop_count}</span> props
                </span>
                {g.edge_count > 0 && (
                  <span>
                    <span className="font-mono font-semibold text-[color:var(--color-accent)]">{g.edge_count}</span> edges
                  </span>
                )}
              </div>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}

