import Link from "next/link";
import { fetchRecentBoard, fetchPlayerHustle } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { HustleStatsResponse } from "@/types/api";

function perGame(total: number | null | undefined, gp: number): string {
  if (total == null) return "--";
  return (total / gp).toFixed(1);
}

interface HustlePlayer {
  player_id: string;
  player_name: string;
  team: string;
  hustle: NonNullable<HustleStatsResponse["season_totals"]>;
  deflPg: number;
  contestedPg: number;
  hustleScore: number;
}

export default async function HustleSpotlight() {
  const { board: boardRes, label } = await fetchRecentBoard();

  // Get unique player IDs from the board (up to 6 to limit fetches)
  const seen = new Set<string>();
  const uniquePlayers: { id: string; name: string; team: string }[] = [];
  for (const p of boardRes.props) {
    if (!seen.has(p.player_id)) {
      seen.add(p.player_id);
      uniquePlayers.push({ id: p.player_id, name: p.player_name, team: p.team_abbreviation });
      if (uniquePlayers.length >= 6) break;
    }
  }

  if (uniquePlayers.length === 0) return null;

  // Fetch hustle stats in parallel
  const hustleResults = await Promise.all(
    uniquePlayers.map((p) =>
      fetchPlayerHustle(p.id).catch(() => null),
    ),
  );

  // Build ranked list
  const hustlePlayers: HustlePlayer[] = [];
  for (let i = 0; i < uniquePlayers.length; i++) {
    const res = hustleResults[i];
    const totals = res?.season_totals;
    if (!totals || !totals.games_played) continue;

    const gp = totals.games_played;
    const deflPg = (totals.deflections ?? 0) / gp;
    const contestedPg = (totals.contested_shots ?? 0) / gp;
    const hustleScore =
      deflPg * 1.5 +
      contestedPg * 1.0 +
      ((totals.charges_drawn ?? 0) / gp) * 2.0 +
      ((totals.screen_assists ?? 0) / gp) * 1.0 +
      ((totals.loose_balls_recovered ?? 0) / gp) * 1.5;

    hustlePlayers.push({
      player_id: uniquePlayers[i].id,
      player_name: uniquePlayers[i].name,
      team: uniquePlayers[i].team,
      hustle: totals,
      deflPg,
      contestedPg,
      hustleScore,
    });
  }

  // Sort by composite hustle score, take top 3
  const top = hustlePlayers.sort((a, b) => b.hustleScore - a.hustleScore).slice(0, 3);

  if (top.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Hustle spotlight
        </p>
        <Badge>{label}</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {top.map((p) => {
          const gp = p.hustle.games_played!;
          const isHighMotor = p.deflPg >= 3 && p.contestedPg >= 8;

          return (
            <Link key={p.player_id} href={`/nba/player/${p.player_id}`}>
              <Card className="cursor-pointer transition-colors hover:border-[color:var(--color-accent)]/40">
                <div className="flex items-center gap-3">
                  <PlayerAvatar playerId={p.player_id} playerName={p.player_name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-semibold">{p.player_name}</span>
                      <span className="text-xs text-[color:var(--color-text-muted)]">{p.team}</span>
                    </div>
                    {isHighMotor && <Badge tone="success" className="mt-0.5 scale-90">High Motor</Badge>}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(p.hustle.deflections, gp)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">Defl</div>
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(p.hustle.contested_shots, gp)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">Cont</div>
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(p.hustle.loose_balls_recovered, gp)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">LB</div>
                  </div>
                </div>
                <p className="mt-2 text-[10px] text-[color:var(--color-text-muted)]">
                  High-motor players create variance in prop outcomes
                </p>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
