import Link from "next/link";
import { fetchBoard } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ConfidenceBar } from "@/components/board/ConfidenceBar";
import { EdgeDisplay } from "@/components/board/EdgeDisplay";
import { Sparkline } from "@/components/board/Sparkline";
import { HitStrip } from "@/components/board/HitStrip";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { PropBoardRow } from "@/types/api";

function PickCard({ prop }: { prop: PropBoardRow }) {
  const side = prop.recommended_side ?? (prop.edge_over > 0 ? "OVER" : "UNDER");
  const hasRecentValues = prop.recent_values && prop.recent_values.length > 0;

  return (
    <Link href={`/nba/props/${prop.signal_id}`} className="block">
      <Card className="relative overflow-hidden border-l-2 border-l-[color:var(--color-accent)] hover:border-[color:var(--color-accent)]/40">
        {/* Player header */}
        <div className="flex items-center gap-3">
          <PlayerAvatar playerId={prop.player_id} playerName={prop.player_name} size="sm" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold truncate">{prop.player_name}</span>
              <span className="text-xs text-[color:var(--color-text-muted)]">{prop.team_abbreviation}</span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <Badge>{prop.stat_type}</Badge>
              {prop.recommended_side && (
                <Badge tone={prop.recommended_side === "OVER" ? "success" : "danger"}>
                  {prop.recommended_side}
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Line + Edge row */}
        <div className="mt-4 flex items-end justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Line</div>
            <div className="font-mono text-lg font-bold">{prop.line}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Proj</div>
            <div className={`font-mono text-lg font-bold ${prop.projected_value > prop.line ? "text-[color:var(--color-positive)]" : "text-[color:var(--color-negative)]"}`}>
              {prop.projected_value.toFixed(1)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Edge</div>
            <EdgeDisplay edge={prop.edge_over} probability={prop.over_probability} side="over" />
          </div>
        </div>

        {/* Confidence */}
        <div className="mt-3">
          <ConfidenceBar value={prop.confidence} />
        </div>

        {/* Sparkline + Hit strip */}
        {hasRecentValues && (
          <div className="mt-3 flex flex-col items-center gap-1">
            <Sparkline values={prop.recent_values!} line={prop.line} />
            <HitStrip values={prop.recent_values!} line={prop.line} side={side} />
          </div>
        )}

        {/* Matchup */}
        <div className="mt-3 text-xs text-[color:var(--color-text-muted)]">
          {prop.away_team_abbreviation} @ {prop.home_team_abbreviation}
          {prop.key_factor && (
            <>
              {" "}&middot;{" "}
              <span className="truncate">{prop.key_factor}</span>
            </>
          )}
        </div>
      </Card>
    </Link>
  );
}

export default async function TopPicksSection() {
  const boardRes = await fetchBoard({ recommended_only: true }).catch(() => ({
    props: [] as PropBoardRow[],
    meta: { total_count: 0, game_count: 0, updated_at: undefined as string | undefined, stat_types_available: [] },
  }));

  const topPicks = [...boardRes.props]
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);

  if (topPicks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--color-border)] py-16 text-center">
        <p className="text-[color:var(--color-text-secondary)]">
          No strong edges found for tonight&apos;s slate yet.
        </p>
        <p className="mt-1 text-sm text-[color:var(--color-text-muted)]">
          Picks appear here once the model runs and finds recommendations.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {topPicks.map((prop) => (
        <PickCard key={prop.signal_id} prop={prop} />
      ))}
    </div>
  );
}
