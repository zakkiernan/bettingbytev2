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

  const seen = new Set<string>();
  const uniquePlayers: { id: string; name: string; team: string }[] = [];
  for (const prop of boardRes.props) {
    if (!seen.has(prop.player_id)) {
      seen.add(prop.player_id);
      uniquePlayers.push({ id: prop.player_id, name: prop.player_name, team: prop.team_abbreviation });
      if (uniquePlayers.length >= 6) break;
    }
  }

  if (uniquePlayers.length === 0) return null;

  const hustleResults = await Promise.all(
    uniquePlayers.map((player) => fetchPlayerHustle(player.id).catch(() => null)),
  );

  const hustlePlayers: HustlePlayer[] = [];
  for (let i = 0; i < uniquePlayers.length; i++) {
    const player = uniquePlayers[i];
    const response = hustleResults[i];
    const totals = response?.season_totals;
    if (!player || !totals || !totals.games_played) continue;

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
      player_id: player.id,
      player_name: player.name,
      team: player.team,
      hustle: totals,
      deflPg,
      contestedPg,
      hustleScore,
    });
  }

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
        {top.map((player) => {
          const gp = player.hustle.games_played ?? 1;
          const isHighMotor = player.deflPg >= 3 && player.contestedPg >= 8;

          return (
            <Link key={player.player_id} href={`/nba/player/${player.player_id}`}>
              <Card className="cursor-pointer transition-colors hover:border-[color:var(--color-accent)]/40">
                <div className="flex items-center gap-3">
                  <PlayerAvatar playerId={player.player_id} playerName={player.player_name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-semibold">{player.player_name}</span>
                      <span className="text-xs text-[color:var(--color-text-muted)]">{player.team}</span>
                    </div>
                    {isHighMotor && <Badge tone="success" className="mt-0.5 scale-90">High Motor</Badge>}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(player.hustle.deflections, gp)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">Defl</div>
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(player.hustle.contested_shots, gp)}</div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">Cont</div>
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold">{perGame(player.hustle.loose_balls_recovered, gp)}</div>
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