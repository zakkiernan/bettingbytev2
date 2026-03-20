"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { AdvancedTrendsResponse } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  trends: AdvancedTrendsResponse;
}

type MetricKey = "usage_percentage" | "true_shooting_percentage" | "pace" | "offensive_rating";

const metrics: { key: MetricKey; label: string; color: string; format: (v: number) => string }[] = [
  { key: "usage_percentage", label: "Usage %", color: "var(--color-accent)", format: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "true_shooting_percentage", label: "TS%", color: "var(--color-positive)", format: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "pace", label: "Pace", color: "var(--caution)", format: (v) => v.toFixed(1) },
  { key: "offensive_rating", label: "ORtg", color: "var(--color-accent)", format: (v) => v.toFixed(1) },
];

export function AdvancedTrendsChart({ trends }: Props) {
  const [activeMetrics, setActiveMetrics] = useState<Set<MetricKey>>(
    new Set(["usage_percentage", "true_shooting_percentage"]),
  );

  const toggle = (key: MetricKey) => {
    setActiveMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const data = trends.points
    .slice()
    .reverse()
    .map((p, i) => ({
      game: i + 1,
      opponent: p.opponent ?? "",
      usage_percentage: p.usage_percentage != null ? p.usage_percentage * 100 : null,
      true_shooting_percentage: p.true_shooting_percentage != null ? p.true_shooting_percentage * 100 : null,
      pace: p.pace,
      offensive_rating: p.offensive_rating,
    }));

  return (
    <Card className="space-y-4">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Scoring profile
      </p>

      <div className="flex flex-wrap gap-2">
        {metrics.map((m) => (
          <button
            key={m.key}
            onClick={() => toggle(m.key)}
            className={`rounded-lg border px-3 py-1 text-xs font-medium transition-colors ${
              activeMetrics.has(m.key)
                ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-muted)] text-[color:var(--color-accent)]"
                : "border-[color:var(--color-border)] text-[color:var(--color-text-muted)] hover:text-[color:var(--color-text-secondary)]"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <XAxis dataKey="game" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "0.75rem",
                fontSize: "0.75rem",
              }}
              labelFormatter={(l: any) => `Game ${l}`}
            />
            {metrics
              .filter((m) => activeMetrics.has(m.key))
              .map((m) => (
                <Line
                  key={m.key}
                  type="monotone"
                  dataKey={m.key}
                  name={m.label}
                  stroke={m.color}
                  strokeWidth={2}
                  dot={{ r: 2, strokeWidth: 0 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
