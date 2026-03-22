"use client";

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { RotationProfile } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  rotation: RotationProfile;
}

function RateBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-[color:var(--color-text-secondary)]">{label}</span>
        <span className="font-mono font-semibold">{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[color:var(--color-surface-elevated)]">
        <div
          className="h-full rounded-full bg-[color:var(--color-accent)]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RotationProfileCard({ rotation }: Props) {
  const minutesData = rotation.recent_games
    .slice()
    .reverse()
    .map((g, i) => ({
      game: i + 1,
      minutes: g.total_shift_duration_real
        ? Math.round(g.total_shift_duration_real / 600)
        : 0,
      opponent: g.opponent ?? "",
    }));

  return (
    <Card className="space-y-4">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Rotation profile
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <RateBar label="Start rate" value={rotation.start_rate} />
        <RateBar label="Close rate" value={rotation.close_rate} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-3 py-2 text-center">
          <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Avg stints</div>
          <div className="mt-1 font-mono text-lg font-semibold">{rotation.avg_stint_count.toFixed(1)}</div>
        </div>
        <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-3 py-2 text-center">
          <div className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Avg minutes</div>
          <div className="mt-1 font-mono text-lg font-semibold">{rotation.avg_minutes.toFixed(1)}</div>
        </div>
      </div>

      {minutesData.length > 0 && (
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <BarChart data={minutesData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis dataKey="game" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "0.75rem",
                  fontSize: "0.75rem",
                }}
                formatter={(v: any) => [`${v} min`, "Minutes"]}
                labelFormatter={(l: any) => `Game ${l}`}
              />
              <Bar dataKey="minutes" fill="var(--color-accent)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
