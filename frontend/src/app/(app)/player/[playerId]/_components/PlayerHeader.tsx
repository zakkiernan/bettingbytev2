import Link from "next/link";

import { fetchPlayerProfile } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PlayerAvatar } from "@/components/ui/player-avatar";

export async function PlayerHeader({ playerId }: { playerId: string }) {
  const profile = await fetchPlayerProfile(playerId).catch(() => null);

  if (!profile) {
    return (
      <div className="py-20 text-center text-[color:var(--color-text-secondary)]">
        Player not found.
      </div>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <PlayerAvatar playerId={playerId} playerName={profile.full_name} size="lg" />
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Player profile</p>
            <h1 className="text-2xl font-bold">{profile.full_name}</h1>
            <p className="mt-1 text-sm text-[color:var(--color-text-secondary)]">
              {profile.team_abbreviation} · {profile.team_full_name}
            </p>
          </div>
        </div>
        <Badge>{profile.season_averages.games_played} games</Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat title="PPG" value={profile.season_averages.ppg.toFixed(1)} />
        <Stat title="RPG" value={profile.season_averages.rpg.toFixed(1)} />
        <Stat title="APG" value={profile.season_averages.apg.toFixed(1)} />
        <Stat title="MPG" value={profile.season_averages.mpg.toFixed(1)} />
        <Stat title="TS%" value={`${(profile.season_averages.ts_pct * 100).toFixed(1)}%`} />
      </div>

      {/* Active props */}
      <Card>
        <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Tonight&apos;s active props</p>
        {profile.active_props.length === 0 ? (
          <p className="text-sm text-[color:var(--color-text-secondary)]">No active props for this player tonight.</p>
        ) : (
          <div className="space-y-3">
            {profile.active_props.map((prop) => (
              <Link key={prop.signal_id} href={`/props/${prop.signal_id}`}>
                <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 transition-colors hover:border-[color:var(--color-border)]">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{prop.stat_type}</span>
                        {prop.recommended_side && (
                          <Badge tone={prop.recommended_side === "OVER" ? "success" : "danger"}>{prop.recommended_side}</Badge>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-[color:var(--color-text-muted)]">
                        {prop.away_team_abbreviation} @ {prop.home_team_abbreviation}
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <MiniStat label="Line" value={prop.line.toFixed(1)} />
                      <MiniStat label="Proj" value={prop.projected_value.toFixed(1)} />
                      <MiniStat label="Edge" value={`${prop.edge_over >= 0 ? "+" : ""}${prop.edge_over.toFixed(1)}`} accent={prop.edge_over >= 0} />
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </Card>
  );
}

function Stat({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 text-center">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{title}</div>
      <div className="mt-1 font-mono text-2xl font-bold">{value}</div>
    </div>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{label}</div>
      <div className={`font-mono text-sm font-semibold ${accent ? "text-[color:var(--color-positive)]" : ""}`}>{value}</div>
    </div>
  );
}
