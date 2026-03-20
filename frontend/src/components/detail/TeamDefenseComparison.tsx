import type { TeamGameContext } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  home: TeamGameContext;
  away: TeamGameContext;
}

function DefStat({ label, home, away, lower }: { label: string; home?: number; away?: number; lower?: boolean }) {
  const homeStr = home != null ? home.toFixed(1) : "—";
  const awayStr = away != null ? away.toFixed(1) : "—";

  let homeColor = "";
  let awayColor = "";
  if (home != null && away != null) {
    const better = lower ? home < away : home > away;
    homeColor = better ? "text-[color:var(--color-positive)]" : "text-[color:var(--color-negative)]";
    awayColor = better ? "text-[color:var(--color-negative)]" : "text-[color:var(--color-positive)]";
  }

  return (
    <tr className="border-b border-[color:var(--color-border)]">
      <td className={`py-2 pr-4 text-right font-mono font-semibold ${awayColor}`}>{awayStr}</td>
      <td className="py-2 px-4 text-center text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{label}</td>
      <td className={`py-2 pl-4 font-mono font-semibold ${homeColor}`}>{homeStr}</td>
    </tr>
  );
}

export function TeamDefenseComparison({ home, away }: Props) {
  const hd = home.defense;
  const ad = away.defense;

  if (!hd && !ad) return null;

  return (
    <Card className="space-y-3">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Team defense comparison
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[color:var(--color-border)]">
            <th className="pb-2 text-right text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              {away.team_abbreviation}
            </th>
            <th className="pb-2 text-center text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Stat</th>
            <th className="pb-2 text-left text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              {home.team_abbreviation}
            </th>
          </tr>
        </thead>
        <tbody>
          <DefStat label="Def Rtg" home={hd?.defensive_rating} away={ad?.defensive_rating} lower />
          <DefStat label="Pace" home={hd?.pace} away={ad?.pace} />
          <DefStat label="Opp PPG" home={hd?.opponent_points_per_game} away={ad?.opponent_points_per_game} lower />
          <DefStat label="Opp FG%" home={hd?.opponent_field_goal_percentage} away={ad?.opponent_field_goal_percentage} lower />
          <DefStat label="Opp 3P%" home={hd?.opponent_three_point_percentage} away={ad?.opponent_three_point_percentage} lower />
        </tbody>
      </table>
    </Card>
  );
}
