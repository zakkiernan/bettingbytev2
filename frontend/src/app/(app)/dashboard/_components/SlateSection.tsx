import { fetchGamesToday } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

export default async function SlateSection() {
  const games = await fetchGamesToday().catch(() => []);

  if (games.length === 0) {
    return (
      <p className="text-sm text-[color:var(--color-text-secondary)]">
        No games found for today.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {games.map((g) => {
        const time = g.game_time_utc
          ? new Date(g.game_time_utc).toLocaleTimeString("en-US", {
              hour: "numeric",
              minute: "2-digit",
              timeZone: "America/New_York",
            })
          : null;
        return (
          <Link key={g.game_id} href={`/games/${g.game_id}`}>
            <Card className="cursor-pointer">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold">
                    {g.away_team.abbreviation}{" "}
                    <span className="text-[color:var(--color-text-muted)]">
                      @
                    </span>{" "}
                    {g.home_team.abbreviation}
                  </div>
                  {time && (
                    <div className="mt-0.5 text-xs text-[color:var(--color-text-muted)]">
                      {time} ET
                    </div>
                  )}
                </div>
                {g.edge_count > 0 && (
                  <Badge tone="success">{g.edge_count} edges</Badge>
                )}
              </div>
              <div className="mt-3 flex gap-3 text-xs text-[color:var(--color-text-muted)]">
                <span>
                  <span className="font-mono text-[color:var(--color-text-primary)]">
                    {g.prop_count}
                  </span>{" "}
                  props
                </span>
              </div>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
