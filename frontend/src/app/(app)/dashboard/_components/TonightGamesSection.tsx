import Link from "next/link";
import { fetchGamesToday } from "@/lib/api";
import { Card } from "@/components/ui/card";

export default async function TonightGamesSection() {
  const games = await fetchGamesToday().catch(() => []);

  if (games.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--color-border)] py-12 text-center">
        <p className="text-[color:var(--color-text-secondary)]">No games scheduled for tonight.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
            <Card className="cursor-pointer">
              <div className="flex items-center justify-between">
                <div className="font-semibold">
                  {g.away_team.abbreviation}{" "}
                  <span className="text-[color:var(--color-text-muted)]">@</span>{" "}
                  {g.home_team.abbreviation}
                </div>
                {time && (
                  <span className="font-mono text-xs text-[color:var(--color-text-muted)]">{time}</span>
                )}
              </div>
              <div className="mt-2 flex gap-3 text-xs text-[color:var(--color-text-muted)]">
                <span>
                  <span className="font-mono font-semibold text-[color:var(--color-text-secondary)]">
                    {g.prop_count}
                  </span>{" "}
                  props
                </span>
                {g.edge_count > 0 && (
                  <span>
                    <span className="font-mono font-semibold text-[color:var(--color-accent)]">
                      {g.edge_count}
                    </span>{" "}
                    edges
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
