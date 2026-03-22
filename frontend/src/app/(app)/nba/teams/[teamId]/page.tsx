import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { fetchTeamProfile } from "@/lib/nba-api";
import { Card } from "@/components/ui/card";
import { LineupLab } from "@/components/stats/LineupLab";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ teamId: string }>;
}

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

export default async function TeamPage({ params }: PageProps) {
  const { teamId } = await params;
  const profile = await fetchTeamProfile(teamId).catch(() => null);

  if (!profile) {
    return (
      <div className="space-y-4">
        <Link
          href="/nba/games"
          className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to games
        </Link>
        <p className="py-20 text-center text-[color:var(--color-text-secondary)]">Team not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href="/nba/games"
        className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to games
      </Link>

      <Card>
        <h1 className="text-2xl font-bold">{profile.team_name}</h1>
        <p className="text-sm text-[color:var(--color-text-muted)]">
          {profile.team_abbreviation}
        </p>
      </Card>

      {/* Team Defense Profile */}
      {profile.defense && (
        <Card>
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Defense profile
          </p>
          <div className="grid gap-3 sm:grid-cols-5">
            <DefStat label="Def Rating" value={fmt(profile.defense.defensive_rating)} />
            <DefStat label="Pace" value={fmt(profile.defense.pace)} />
            <DefStat label="Opp PPG" value={fmt(profile.defense.opponent_points_per_game)} />
            <DefStat label="Opp FG%" value={pct(profile.defense.opponent_field_goal_percentage)} />
            <DefStat label="Opp 3P%" value={pct(profile.defense.opponent_three_point_percentage)} />
          </div>
        </Card>
      )}

      {/* Lineup Lab */}
      {profile.lineups.lineups.length > 0 && (
        <Card>
          <LineupLab lineups={profile.lineups.lineups} />
        </Card>
      )}
    </div>
  );
}

function DefStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-3 py-2.5 text-center">
      <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)]">{label}</div>
      <div className="mt-0.5 font-mono text-lg font-bold">{value}</div>
    </div>
  );
}
