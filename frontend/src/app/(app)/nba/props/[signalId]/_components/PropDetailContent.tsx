import Link from "next/link";

import { fetchPropDetail, fetchLineMovement } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { BreakdownTable } from "@/components/detail/BreakdownTable";
import { GameLogTable } from "@/components/detail/GameLogTable";
import { InjuryPanel } from "@/components/detail/InjuryPanel";
import { OpportunityPanel } from "@/components/detail/OpportunityPanel";
import { LineupContextCard } from "@/components/detail/LineupContextCard";
import { AbsenceStories } from "@/components/detail/AbsenceStories";
import { TrendChart } from "@/components/detail/TrendChart";
import { LineMovement } from "@/components/board/LineMovement";
import { ConfidenceBar } from "@/components/board/ConfidenceBar";
import { ContextTag } from "@/components/board/ContextTag";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import { ShootingContext } from "./ShootingContext";

export async function PropDetailContent({ signalId }: { signalId: number }) {
  const [prop, lineMovement] = await Promise.all([
    fetchPropDetail(signalId).catch(() => null),
    fetchLineMovement(signalId).catch(() => null),
  ]);

  if (!prop) {
    return (
      <p className="text-[color:var(--color-text-secondary)]">
        Signal #{signalId} not found.
      </p>
    );
  }

  const matchup = `${prop.away_team_abbreviation} @ ${prop.home_team_abbreviation}`;
  const gameTime = prop.game_time_utc
    ? new Date(prop.game_time_utc).toLocaleString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/New_York",
      })
    : null;

  const edgeOver = prop.edge_over;
  const edgeColor =
    edgeOver > 0
      ? "text-[color:var(--color-positive)]"
      : "text-[color:var(--color-negative)]";
  const edgeDirection = edgeOver >= 0 ? "OVER" : "UNDER";
  const contextSource = prop.features.context_source ?? "none";
  const hitRate =
    prop.recent_games_count && prop.recent_games_count > 0 && prop.recent_hit_rate != null
      ? `${Math.round(prop.recent_hit_rate * 100)}% over ${prop.recent_games_count}`
      : "\u2014";

  const hasNarrative =
    prop.narrative &&
    (prop.narrative.lineup_context || prop.narrative.absence_stories.length > 0);

  const hasRecentValues = prop.recent_values && prop.recent_values.length > 0;

  return (
    <>
      <div className="flex flex-wrap items-center justify-end">
        <Link
          href={`/nba/player/${prop.player_id}`}
          className="inline-flex rounded-xl border border-[color:var(--color-border)] px-3 py-2 text-sm text-[color:var(--color-text-secondary)] transition-colors hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-text-primary)]"
        >
          Open player profile
        </Link>
      </div>

      {/* The Verdict */}
      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <PlayerAvatar playerId={prop.player_id} playerName={prop.player_name} size="md" />
              <h1 className="text-2xl font-bold">{prop.player_name}</h1>
              <span className="text-[color:var(--color-text-muted)]">
                {prop.team_abbreviation}
              </span>
              <Badge>{prop.stat_type}</Badge>
              {prop.recommended_side && (
                <Badge tone={prop.recommended_side === "OVER" ? "success" : "danger"}>
                  {prop.recommended_side}
                </Badge>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[color:var(--color-text-muted)]">
              <span>{matchup}</span>
              {gameTime && (
                <>
                  <span>&middot;</span>
                  <span>{gameTime}</span>
                </>
              )}
            </div>
          </div>
          <ContextTag source={contextSource} />
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <SummaryStat title="Line" value={prop.line.toFixed(1)} />
          <SummaryStat title="Projection" value={prop.projected_value.toFixed(1)} accent />
          <SummaryStat
            title="Model lean"
            value={`${edgeDirection} ${Math.abs(edgeOver).toFixed(1)}`}
            className={edgeColor}
          />
          <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/60 px-4 py-3 text-center">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              Confidence
            </div>
            <div className="flex justify-center">
              <ConfidenceBar value={prop.confidence} />
            </div>
          </div>
          <SummaryStat title="Recent hit rate" value={hitRate} />
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-4 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
              Market view
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <OddsRow label="Over" odds={prop.over_odds} probability={prop.over_probability} />
              <OddsRow label="Under" odds={prop.under_odds} probability={prop.under_probability} />
            </div>
            {lineMovement && lineMovement.opening_line != null && (
              <div className="mt-3 flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)]">
                <span className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Line movement</span>
                <LineMovement openingLine={lineMovement.opening_line} currentLine={lineMovement.current_line} />
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-4 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
              Model note
            </p>
            <p className="mt-3 text-sm leading-6 text-[color:var(--color-text-secondary)]">
              {prop.key_factor ?? "No single key factor was attached to this signal."}
            </p>
          </div>
        </div>
      </Card>

      {/* The Narrative */}
      {hasNarrative && (
        <div className="grid gap-6 lg:grid-cols-2">
          {prop.narrative!.lineup_context && (
            <LineupContextCard context={prop.narrative!.lineup_context} />
          )}
          {prop.narrative!.absence_stories.length > 0 && (
            <AbsenceStories stories={prop.narrative!.absence_stories} />
          )}
        </div>
      )}

      {/* The Evidence */}
      {hasRecentValues && (
        <Card>
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Recent performance vs line
          </p>
          <TrendChart
            values={prop.recent_values!}
            line={prop.line}
            statLabel={prop.stat_type}
          />
        </Card>
      )}

      <Card>
        <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Recent game log
        </p>
        <GameLogTable
          log={prop.recent_game_log}
          line={prop.line}
          highlightStat={prop.stat_type}
        />
      </Card>

      {/* Scoring profile context */}
      <ShootingContext playerId={prop.player_id} statType={prop.stat_type} />

      {/* The Model */}
      <details className="group">
        <summary className="cursor-pointer list-none rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/80 px-5 py-3 text-sm font-medium text-[color:var(--color-text-secondary)] transition-colors hover:border-[color:var(--color-border)]">
          <span className="mr-2 inline-block transition-transform group-open:rotate-90">&#x25B8;</span>
          Model details
        </summary>

        <div className="mt-4 space-y-6">
          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <Card>
              <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
                Points breakdown
              </p>
              <BreakdownTable breakdown={prop.breakdown} />
            </Card>

            <Card>
              <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
                Opportunity context
              </p>
              <OpportunityPanel opportunity={prop.opportunity} />
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <Card>
              <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
                Team context snapshot
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <MiniSnapshot label="Home/Away" value={prop.features.is_home ? "Home" : "Away"} />
                <MiniSnapshot label="Sample size" value={String(prop.features.sample_size)} />
                <MiniSnapshot label="Rest" value={prop.features.days_rest != null ? `${prop.features.days_rest} days` : "\u2014"} />
                <MiniSnapshot label="Back-to-back" value={prop.features.back_to_back ? "Yes" : "No"} />
                <MiniSnapshot label="Season avg" value={prop.features.season_points_avg != null ? prop.features.season_points_avg.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Last 10" value={prop.features.last10_points_avg != null ? prop.features.last10_points_avg.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Last 5" value={prop.features.last5_points_avg != null ? prop.features.last5_points_avg.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Season minutes" value={prop.features.season_minutes_avg != null ? prop.features.season_minutes_avg.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Usage" value={prop.features.season_usage_pct != null ? `${(prop.features.season_usage_pct * 100).toFixed(1)}%` : "\u2014"} />
                <MiniSnapshot label="Team pace" value={prop.features.team_pace != null ? prop.features.team_pace.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Opponent pace" value={prop.features.opponent_pace != null ? prop.features.opponent_pace.toFixed(1) : "\u2014"} />
                <MiniSnapshot label="Opp def rtg" value={prop.features.opponent_def_rating != null ? prop.features.opponent_def_rating.toFixed(1) : "\u2014"} />
              </div>
            </Card>

            <Card>
              <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
                Official injury report &mdash; {prop.team_abbreviation}
              </p>
              <InjuryPanel entries={prop.opportunity.injury_entries} teamAbbr={prop.team_abbreviation} />
            </Card>
          </div>
        </div>
      </details>
    </>
  );
}

function SummaryStat({
  title,
  value,
  accent,
  className,
}: {
  title: string;
  value: string;
  accent?: boolean;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border px-4 py-3 text-center ${accent ? "border-[color:var(--color-accent)]/30 bg-[color:var(--color-accent-muted)]" : "border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/60"}`}>
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
        {title}
      </div>
      <div className={`mt-1 font-mono text-2xl font-bold ${accent ? "text-[color:var(--color-accent)]" : ""} ${className ?? ""}`}>
        {value}
      </div>
    </div>
  );
}

function OddsRow({
  label,
  odds,
  probability,
}: {
  label: string;
  odds: number;
  probability: number;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-background)]/50 px-3 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg font-semibold">
        {odds > 0 ? "+" : ""}
        {odds}
      </div>
      <div className="mt-1 text-xs text-[color:var(--color-text-muted)]">
        implied {Math.round(probability * 100)}%
      </div>
    </div>
  );
}

function MiniSnapshot({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-3 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm font-semibold">{value}</div>
    </div>
  );
}

