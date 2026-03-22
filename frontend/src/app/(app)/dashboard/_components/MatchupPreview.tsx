import Link from "next/link";
import { fetchRecentBoard, fetchPlayerDefense } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { DefensiveZone } from "@/types/api";

function pct(value: number | null | undefined): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

export default async function MatchupPreview() {
  const { board: boardRes, label } = await fetchRecentBoard();

  const pointProps = boardRes.props.filter((prop) => prop.stat_type === "points");
  if (pointProps.length === 0) return null;

  const topScorer = [...pointProps].sort((a, b) => b.projected_value - a.projected_value)[0];
  if (!topScorer) return null;

  const scorerIsHome = topScorer.team_abbreviation === topScorer.home_team_abbreviation;
  const opponentTeam = scorerIsHome
    ? topScorer.away_team_abbreviation
    : topScorer.home_team_abbreviation;

  const opponentPlayers = boardRes.props.filter(
    (prop) => prop.game_id === topScorer.game_id && prop.team_abbreviation === opponentTeam,
  );

  const seen = new Set<string>();
  const uniqueOpponents: { id: string; name: string }[] = [];
  for (const player of opponentPlayers) {
    if (!seen.has(player.player_id)) {
      seen.add(player.player_id);
      uniqueOpponents.push({ id: player.player_id, name: player.player_name });
      if (uniqueOpponents.length >= 4) break;
    }
  }

  if (uniqueOpponents.length === 0) return null;

  const defenseResults = await Promise.all(
    uniqueOpponents.map((player) => fetchPlayerDefense(player.id).catch(() => null)),
  );

  let bestDefender: { id: string; name: string; overall: DefensiveZone } | null = null;
  let bestDelta = Infinity;

  for (let i = 0; i < uniqueOpponents.length; i++) {
    const opponent = uniqueOpponents[i];
    const response = defenseResults[i];
    if (!opponent || !response?.zones?.length) continue;

    const overall = response.zones.find((zone) => zone.defense_category === "Overall");
    if (!overall || overall.pct_plusminus == null) continue;

    if (overall.pct_plusminus < bestDelta) {
      bestDelta = overall.pct_plusminus;
      bestDefender = { id: opponent.id, name: opponent.name, overall };
    }
  }

  if (!bestDefender) return null;

  const isToughMatchup = bestDelta < -0.03;
  const isFavorableMatchup = bestDelta > 0.02;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Matchup of the night
        </p>
        <Badge>{label}</Badge>
      </div>
      <Card>
        <div className="flex items-center justify-between gap-4">
          <Link href={`/nba/player/${topScorer.player_id}`} className="flex min-w-0 items-center gap-3">
            <PlayerAvatar playerId={topScorer.player_id} playerName={topScorer.player_name} size="md" />
            <div className="min-w-0">
              <p className="truncate font-semibold">{topScorer.player_name}</p>
              <p className="text-xs text-[color:var(--color-text-muted)]">{topScorer.team_abbreviation}</p>
              <div className="mt-1 flex items-center gap-2">
                <span className="font-mono text-sm font-bold">{topScorer.projected_value.toFixed(1)}</span>
                <span className="text-[10px] uppercase text-[color:var(--color-text-muted)]">Proj PTS</span>
              </div>
            </div>
          </Link>

          <div className="flex flex-col items-center gap-1 px-2">
            <span className="text-xs font-bold text-[color:var(--color-text-muted)]">VS</span>
            {isToughMatchup && <Badge tone="danger">Tough</Badge>}
            {isFavorableMatchup && <Badge tone="success">Favorable</Badge>}
            {!isToughMatchup && !isFavorableMatchup && <Badge>Neutral</Badge>}
          </div>

          <Link href={`/nba/player/${bestDefender.id}`} className="flex min-w-0 items-center gap-3 text-right">
            <div className="min-w-0">
              <p className="truncate font-semibold">{bestDefender.name}</p>
              <p className="text-xs text-[color:var(--color-text-muted)]">{opponentTeam}</p>
              <div className="mt-1 flex items-center justify-end gap-2">
                <span className="text-[10px] uppercase text-[color:var(--color-text-muted)]">D-FG%</span>
                <span className="font-mono text-sm font-bold">
                  {pct(bestDefender.overall.d_fg_pct)}
                </span>
              </div>
            </div>
            <PlayerAvatar playerId={bestDefender.id} playerName={bestDefender.name} size="md" />
          </Link>
        </div>

        <div className="mt-3 flex items-center justify-center gap-4 border-t border-[color:var(--color-border-subtle)] pt-3 text-xs text-[color:var(--color-text-muted)]">
          <span>
            {topScorer.away_team_abbreviation} @ {topScorer.home_team_abbreviation}
          </span>
          <span>&middot;</span>
          <span>
            Opponent FG%{" "}
            <span
              className={
                bestDelta < 0
                  ? "font-semibold text-[color:var(--color-positive)]"
                  : "font-semibold text-[color:var(--color-negative)]"
              }
            >
              {bestDelta > 0 ? "+" : ""}
              {(bestDelta * 100).toFixed(1)}%
            </span>
            {" "}vs league avg
          </span>
        </div>
      </Card>
    </div>
  );
}