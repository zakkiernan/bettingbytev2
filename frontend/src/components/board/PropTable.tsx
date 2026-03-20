"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { ConfidenceBar } from "@/components/board/ConfidenceBar";
import { ContextTag } from "@/components/board/ContextTag";
import { EdgeDisplay } from "@/components/board/EdgeDisplay";
import { HitStrip } from "@/components/board/HitStrip";
import { LineMovement } from "@/components/board/LineMovement";
import { Sparkline } from "@/components/board/Sparkline";
import { PlayerAvatar } from "@/components/ui/player-avatar";
import type { GameDetailResponse, PropBoardRow } from "@/types/api";

function GameTabs({
  games,
  active,
  onSelect,
}: {
  games: GameDetailResponse[];
  active: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onSelect(null)}
        className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
          active === null
            ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-muted)] text-[color:var(--color-accent)]"
            : "border-[color:var(--color-border)] text-[color:var(--color-text-secondary)] hover:border-[color:var(--color-border)] hover:text-[color:var(--color-text-primary)]"
        }`}
      >
        All games
      </button>
      {games.map((g) => {
        const label = `${g.away_team.abbreviation} @ ${g.home_team.abbreviation}`;
        const time = g.game_time_utc
          ? new Date(g.game_time_utc).toLocaleTimeString("en-US", {
              hour: "numeric",
              minute: "2-digit",
              timeZone: "America/New_York",
            })
          : "";
        return (
          <button
            key={g.game_id}
            onClick={() => onSelect(g.game_id)}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              active === g.game_id
                ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-muted)] text-[color:var(--color-accent)]"
                : "border-[color:var(--color-border)] text-[color:var(--color-text-secondary)] hover:border-[color:var(--color-border)] hover:text-[color:var(--color-text-primary)]"
            }`}
          >
            <span>{label}</span>
            {time && (
              <span className="text-[color:var(--color-text-muted)]">{time}</span>
            )}
            {g.edge_count > 0 && (
              <span className="rounded-full bg-[color:var(--color-accent-hover)] px-1.5 py-0.5 text-[10px] text-[color:var(--color-accent)]">
                {g.edge_count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function StatTypeTabs({
  statTypes,
  active,
  onSelect,
}: {
  statTypes: string[];
  active: string | null;
  onSelect: (s: string | null) => void;
}) {
  const labels: Record<string, string> = {
    points: "Points",
    rebounds: "Rebounds",
    assists: "Assists",
    threes: "Threes",
    steals: "Steals",
    blocks: "Blocks",
  };

  return (
    <div className="flex gap-1 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/60 p-1">
      <button
        onClick={() => onSelect(null)}
        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
          active === null
            ? "bg-[color:var(--color-accent)] text-white"
            : "text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
        }`}
      >
        All
      </button>
      {statTypes.map((st) => (
        <button
          key={st}
          onClick={() => onSelect(st)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            active === st
              ? "bg-[color:var(--color-accent)] text-white"
              : "text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
          }`}
        >
          {labels[st] ?? st}
        </button>
      ))}
    </div>
  );
}

function FiltersBar({
  recommendedOnly,
  onRecommendedOnly,
  minConfidence,
  onMinConfidence,
  search,
  onSearch,
  sortBy,
  onSortBy,
  totalShown,
  totalAll,
}: {
  recommendedOnly: boolean;
  onRecommendedOnly: (v: boolean) => void;
  minConfidence: number;
  onMinConfidence: (v: number) => void;
  search: string;
  onSearch: (v: string) => void;
  sortBy: "confidence" | "edge" | "projection";
  onSortBy: (v: "confidence" | "edge" | "projection") => void;
  totalShown: number;
  totalAll: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/60 px-4 py-3">
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={recommendedOnly}
          onChange={(e) => onRecommendedOnly(e.target.checked)}
          className="h-4 w-4 accent-[color:var(--color-accent)]"
        />
        <span className="text-[color:var(--color-text-secondary)]">
          Recommended only
        </span>
      </label>

      <label className="flex items-center gap-2 text-sm">
        <span className="text-[color:var(--color-text-secondary)]">Min confidence</span>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(minConfidence * 100)}
          onChange={(e) => onMinConfidence(Number(e.target.value) / 100)}
          className="w-24 accent-[color:var(--color-accent)]"
        />
        <span className="w-8 font-mono text-xs text-[color:var(--color-text-muted)]">
          {Math.round(minConfidence * 100)}%
        </span>
      </label>

      <input
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search player/team"
        className="min-w-[200px] rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-background)] px-3 py-2 text-sm outline-none placeholder:text-[color:var(--color-text-muted)] focus:border-[color:var(--color-accent)]"
      />

      <select
        value={sortBy}
        onChange={(e) => onSortBy(e.target.value as "confidence" | "edge" | "projection")}
        className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-background)] px-3 py-2 text-sm text-[color:var(--color-text-secondary)] outline-none focus:border-[color:var(--color-accent)]"
      >
        <option value="confidence">Sort: confidence</option>
        <option value="edge">Sort: edge</option>
        <option value="projection">Sort: projection</option>
      </select>

      <span className="ml-auto font-mono text-xs text-[color:var(--color-text-muted)]">
        {totalShown} / {totalAll} props
      </span>
    </div>
  );
}

function PropRow({ prop }: { prop: PropBoardRow }) {
  const matchup = `${prop.away_team_abbreviation} @ ${prop.home_team_abbreviation}`;
  const projVsLine = prop.projected_value - prop.line;
  const projColor =
    projVsLine > 0
      ? "text-[color:var(--color-positive)]"
      : "text-[color:var(--color-negative)]";

  const hasRecentValues = prop.recent_values && prop.recent_values.length > 0;
  const side = prop.recommended_side ?? (prop.edge_over > 0 ? "OVER" : "UNDER");

  return (
    <div className="grid grid-cols-1 gap-3 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/80 px-4 py-3 transition-colors hover:border-[color:var(--color-border)] hover:bg-[color:var(--color-surface-elevated)]/80 lg:grid-cols-[1.2fr_auto_auto_auto_auto_auto_auto_auto_auto] lg:items-center lg:gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <PlayerAvatar playerId={prop.player_id} playerName={prop.player_name} size="sm" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/player/${prop.player_id}`} className="font-semibold hover:text-[color:var(--color-accent)]">
              {prop.player_name}
            </Link>
          <span className="text-xs text-[color:var(--color-text-muted)]">
            {prop.team_abbreviation}
          </span>
          <Badge>{prop.stat_type}</Badge>
          {prop.recommended_side && (
            <Badge tone={prop.recommended_side === "OVER" ? "success" : "danger"}>
              {prop.recommended_side}
            </Badge>
          )}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-[color:var(--color-text-muted)]">
          <span>{matchup}</span>
          {prop.key_factor && (
            <>
              <span>·</span>
              <span className="truncate max-w-[320px]">{prop.key_factor}</span>
            </>
          )}
        </div>
        </div>
      </div>

      <Metric label="Line" value={prop.line} mono />
      <Metric label="Proj" value={prop.projected_value.toFixed(1)} mono className={projColor} />
      <div className="text-center">
        <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Edge</div>
        <EdgeDisplay edge={prop.edge_over} probability={prop.over_probability} side="over" />
      </div>
      <Metric
        label="Odds"
        value={`${prop.over_odds > 0 ? "+" : ""}${prop.over_odds} / ${prop.under_odds > 0 ? "+" : ""}${prop.under_odds}`}
        mono
        small
      />
      <div>
        <div className="mb-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Conf</div>
        <ConfidenceBar value={prop.confidence} />
      </div>

      {/* Sparkline + Hit strip */}
      <div className="flex flex-col items-center gap-1">
        {hasRecentValues ? (
          <>
            <Sparkline values={prop.recent_values!} line={prop.line} />
            <HitStrip values={prop.recent_values!} line={prop.line} side={side} />
          </>
        ) : (
          <span className="text-xs text-[color:var(--color-text-muted)]">—</span>
        )}
      </div>

      {/* Line movement */}
      <div>
        <div className="mb-1 text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Move</div>
        {prop.opening_line != null ? (
          <LineMovement openingLine={prop.opening_line} currentLine={prop.line} />
        ) : (
          <span className="text-xs text-[color:var(--color-text-muted)]">—</span>
        )}
      </div>

      <div className="text-right">
        <Link href={`/props/${prop.signal_id}`} className="inline-flex rounded-xl border border-[color:var(--color-border)] px-3 py-2 text-sm text-[color:var(--color-text-secondary)] transition-colors hover:border-[color:var(--color-accent)] hover:text-[color:var(--color-text-primary)]">
          Open
        </Link>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  mono,
  small,
  className,
}: {
  label: string;
  value: string | number;
  mono?: boolean;
  small?: boolean;
  className?: string;
}) {
  return (
    <div className="text-center">
      <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{label}</div>
      <div className={`${mono ? "font-mono" : ""} ${small ? "text-xs" : "text-sm"} font-semibold ${className ?? ""}`}>
        {value}
      </div>
    </div>
  );
}

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--color-border)] py-20 text-center">
      <p className="text-[color:var(--color-text-secondary)]">
        {filtered
          ? "No props match the current filters."
          : "No signals for tonight's slate yet."}
      </p>
      {filtered ? (
        <p className="mt-1 text-sm text-[color:var(--color-text-muted)]">
          Try loosening confidence, search, or recommended-only.
        </p>
      ) : (
        <p className="mt-1 text-sm text-[color:var(--color-text-muted)]">
          Run the model to generate tonight's signals.
        </p>
      )}
    </div>
  );
}

interface Props {
  initialProps: PropBoardRow[];
  games: GameDetailResponse[];
  statTypes?: string[];
}

export function PropTable({ initialProps, games, statTypes = [] }: Props) {
  const [activeGame, setActiveGame] = useState<string | null>(null);
  const [activeStat, setActiveStat] = useState<string | null>(null);
  const [recommendedOnly, setRecommendedOnly] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"confidence" | "edge" | "projection">("confidence");

  const visible = useMemo(() => {
    const filtered = initialProps.filter((p) => {
      if (activeGame && p.game_id !== activeGame) return false;
      if (activeStat && p.stat_type !== activeStat) return false;
      if (recommendedOnly && p.recommended_side == null) return false;
      if (p.confidence < minConfidence) return false;
      if (search) {
        const q = search.toLowerCase();
        const haystack = `${p.player_name} ${p.team_abbreviation} ${p.home_team_abbreviation} ${p.away_team_abbreviation}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });

    filtered.sort((a, b) => {
      if (a.recommended_side && !b.recommended_side) return -1;
      if (!a.recommended_side && b.recommended_side) return 1;
      if (sortBy === "edge") return Math.abs(b.edge_over) - Math.abs(a.edge_over);
      if (sortBy === "projection") return b.projected_value - a.projected_value;
      return b.confidence - a.confidence;
    });

    return filtered;
  }, [activeGame, activeStat, recommendedOnly, minConfidence, search, sortBy, initialProps]);

  const isFiltered = activeGame !== null || activeStat !== null || recommendedOnly || minConfidence > 0 || search.length > 0;

  return (
    <div className="space-y-4">
      <GameTabs games={games} active={activeGame} onSelect={setActiveGame} />

      {statTypes.length > 1 && (
        <StatTypeTabs statTypes={statTypes} active={activeStat} onSelect={setActiveStat} />
      )}

      <FiltersBar
        recommendedOnly={recommendedOnly}
        onRecommendedOnly={setRecommendedOnly}
        minConfidence={minConfidence}
        onMinConfidence={setMinConfidence}
        search={search}
        onSearch={setSearch}
        sortBy={sortBy}
        onSortBy={setSortBy}
        totalShown={visible.length}
        totalAll={initialProps.length}
      />

      <div className="space-y-2">
        {visible.length === 0 ? (
          <EmptyState filtered={isFiltered} />
        ) : (
          visible.map((prop) => <PropRow key={prop.signal_id} prop={prop} />)
        )}
      </div>
    </div>
  );
}
