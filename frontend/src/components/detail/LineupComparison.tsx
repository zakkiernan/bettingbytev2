import type { TeamGameContext, LineupEntry, InjuryEntry } from "@/types/api";

interface Props {
  home: TeamGameContext;
  away: TeamGameContext;
}

function StatusDot({ status }: { status?: string }) {
  const colors: Record<string, string> = {
    Out: "bg-[color:var(--color-negative)]",
    Doubtful: "bg-[color:var(--caution)]",
    Questionable: "bg-yellow-400",
    Probable: "bg-[color:var(--color-positive)]",
  };
  if (!status) return null;
  return <span className={`inline-block h-2 w-2 rounded-full ${colors[status] ?? "bg-[color:var(--color-text-muted)]"}`} title={status} />;
}

function PlayerRow({ player, injury }: { player: LineupEntry; injury?: InjuryEntry }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors hover:bg-[color:var(--color-surface-elevated)]/40">
      <div className="flex items-center gap-2">
        {injury && <StatusDot status={injury.current_status} />}
        <span className={player.expected_start ? "font-semibold" : "text-[color:var(--color-text-secondary)]"}>
          {player.player_name ?? "Unknown"}
        </span>
        {player.expected_start && (
          <span className="text-[10px] uppercase tracking-widest text-[color:var(--color-accent)]">S</span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-[color:var(--color-text-muted)]">
        {player.starter_confidence != null && (
          <span>{Math.round(player.starter_confidence * 100)}%</span>
        )}
        {player.late_scratch_risk != null && player.late_scratch_risk > 0.1 && (
          <span className="text-[color:var(--caution)]">scratch {Math.round(player.late_scratch_risk * 100)}%</span>
        )}
      </div>
    </div>
  );
}

function TeamColumn({ team }: { team: TeamGameContext }) {
  const injuryMap = new Map(
    team.injury_entries.map((e) => [e.player_name, e]),
  );

  const starters = team.expected_lineup.filter((p) => p.expected_start);
  const bench = team.expected_lineup.filter((p) => !p.expected_start);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{team.team_name ?? team.team_abbreviation}</span>
        {team.teammate_out_count_top7 != null && team.teammate_out_count_top7 > 0 && (
          <span className="text-xs text-[color:var(--color-negative)]">
            {team.teammate_out_count_top7} top-7 out
          </span>
        )}
      </div>

      {starters.length > 0 && (
        <div>
          <p className="mb-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Projected starters</p>
          <div className="divide-y divide-[color:var(--color-border)]">
            {starters.map((p, i) => (
              <PlayerRow key={p.player_id ?? i} player={p} injury={injuryMap.get(p.player_name ?? "")} />
            ))}
          </div>
        </div>
      )}

      {bench.length > 0 && (
        <div>
          <p className="mb-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Rotation</p>
          <div className="divide-y divide-[color:var(--color-border)]">
            {bench.map((p, i) => (
              <PlayerRow key={p.player_id ?? i} player={p} injury={injuryMap.get(p.player_name ?? "")} />
            ))}
          </div>
        </div>
      )}

      {team.injury_entries.length > 0 && (
        <div>
          <p className="mb-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Injury report</p>
          <div className="space-y-1">
            {team.injury_entries.map((e, i) => (
              <div key={`${e.player_name}-${i}`} className="flex items-center justify-between gap-2 px-3 py-1 text-sm">
                <div className="flex items-center gap-2">
                  <StatusDot status={e.current_status} />
                  <span>{e.player_name}</span>
                </div>
                <span className="text-xs text-[color:var(--color-text-muted)]">{e.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function LineupComparison({ home, away }: Props) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/80 p-4">
        <TeamColumn team={away} />
      </div>
      <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/80 p-4">
        <TeamColumn team={home} />
      </div>
    </div>
  );
}
