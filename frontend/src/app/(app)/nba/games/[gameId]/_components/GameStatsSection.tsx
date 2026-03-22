import { Card } from "@/components/ui/card";
import { ShotChart } from "@/components/charts/ShotChart";
import { WinProbChart } from "@/components/charts/WinProbChart";
import { MatchupGrid } from "@/components/stats/MatchupGrid";
import { HustleBoxScore } from "@/components/stats/HustleBoxScore";
import {
  fetchGameWinProbability,
  fetchGameMatchups,
  fetchGameHustle,
  fetchGameShotChart,
  fetchGameDetail,
} from "@/lib/nba-api";

export async function GameStatsSection({ gameId }: { gameId: string }) {
  const [winProb, matchups, hustle, shotChart, game] = await Promise.all([
    fetchGameWinProbability(gameId).catch(() => null),
    fetchGameMatchups(gameId).catch(() => null),
    fetchGameHustle(gameId).catch(() => null),
    fetchGameShotChart(gameId).catch(() => null),
    fetchGameDetail(gameId).catch(() => null),
  ]);

  const hasAny =
    (winProb?.points.length ?? 0) > 0 ||
    (matchups?.matchups.length ?? 0) > 0 ||
    (hustle?.players.length ?? 0) > 0 ||
    (shotChart?.shots.length ?? 0) > 0;

  if (!hasAny) return null;

  const homeTeam = game?.home_team.abbreviation ?? "Home";
  const awayTeam = game?.away_team.abbreviation ?? "Away";

  return (
    <div className="space-y-6">
      {winProb && winProb.points.length > 0 && (
        <Card>
          <WinProbChart points={winProb.points} homeTeam={homeTeam} awayTeam={awayTeam} />
        </Card>
      )}

      {shotChart && shotChart.shots.length > 0 && (
        <Card>
          <ShotChart
            shots={shotChart.shots}
            title={`Game shot chart \u00b7 ${shotChart.total_shots} total shots`}
          />
        </Card>
      )}

      {matchups && matchups.matchups.length > 0 && (
        <Card>
          <MatchupGrid matchups={matchups.matchups} />
        </Card>
      )}

      {hustle && hustle.players.length > 0 && (
        <Card>
          <HustleBoxScore players={hustle.players} />
        </Card>
      )}
    </div>
  );
}
