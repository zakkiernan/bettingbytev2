import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchLiveGame } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ gameId: string }>;
}

export default async function LiveGamePage({ params }: PageProps) {
  const { gameId } = await params;
  const game = await fetchLiveGame(gameId).catch(() => null);

  if (!game) {
    return <div className="py-20 text-center text-[color:var(--color-text-secondary)]">Live game not found.</div>;
  }

  return (
    <div className="space-y-6">
      <Link href="/nba/live" className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]">
        <ArrowLeft className="h-4 w-4" />
        Back to live center
      </Link>

      <Card className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              {game.away_team.abbreviation} @ {game.home_team.abbreviation}
            </p>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="font-mono text-4xl font-bold">{game.away_score}</span>
              <span className="text-[color:var(--color-text-muted)]">-</span>
              <span className="font-mono text-4xl font-bold">{game.home_score}</span>
            </div>
          </div>
          <Badge tone="live">Q{game.period} · {game.game_clock}</Badge>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat title="Current pace" value={game.pace.current_pace.toFixed(1)} />
          <Stat title="Expected pace" value={game.pace.expected_pace.toFixed(1)} />
          <Stat title="Scoring impact" value={`${game.pace.scoring_impact_pct.toFixed(1)}%`} accent />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
        <Card>
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Live player rows
          </p>
          <div className="space-y-2">
            {game.players.map((player) => (
              <div key={`${player.player_id}-${player.stat_type}`} className="grid grid-cols-2 gap-3 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 md:grid-cols-6">
                <div className="md:col-span-2">
                  <div className="font-semibold">{player.player_name}</div>
                  <div className="text-xs text-[color:var(--color-text-muted)]">{player.team_abbreviation} · {player.stat_type}</div>
                </div>
                <MiniStat label="Current" value={player.current_stat.toFixed(1)} />
                <MiniStat label="Live proj" value={player.live_projection.toFixed(1)} />
                <MiniStat label="Pregame" value={player.pregame_projection.toFixed(1)} />
                <div className="text-right">
                  <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Edge</div>
                  <div className={player.live_edge >= 0 ? "font-mono font-semibold text-[color:var(--color-positive)]" : "font-mono font-semibold text-[color:var(--color-negative)]"}>
                    {player.live_edge >= 0 ? "+" : ""}{player.live_edge.toFixed(1)}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--color-text-muted)]">
                    {player.on_court ? "On court" : "Off court"} · {player.minutes_played.toFixed(1)}m
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
              Alerts
            </p>
            <div className="space-y-3">
              {game.alerts.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <Badge tone="live">{alert.type.replaceAll("_", " ")}</Badge>
                    <span className="text-xs text-[color:var(--color-text-muted)]">
                      {new Date(alert.created_at).toLocaleTimeString("en-US", {
                        hour: "numeric",
                        minute: "2-digit",
                        timeZone: "America/New_York",
                      })}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-medium">{alert.player_name}</p>
                  <p className="mt-1 text-sm text-[color:var(--color-text-secondary)]">{alert.message}</p>
                  {alert.edge_value != null && (
                    <p className="mt-2 font-mono text-sm text-[color:var(--color-accent)]">
                      Edge {alert.edge_value >= 0 ? "+" : ""}{alert.edge_value.toFixed(1)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ title, value, accent }: { title: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 text-center">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{title}</div>
      <div className={`mt-1 font-mono text-2xl font-bold ${accent ? "text-[color:var(--color-accent)]" : ""}`}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{label}</div>
      <div className="font-mono text-sm font-semibold">{value}</div>
    </div>
  );
}

