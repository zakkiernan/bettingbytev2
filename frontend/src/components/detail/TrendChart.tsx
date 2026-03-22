"use client";

import {
  AreaChart,
  Area,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  values: number[];
  line: number;
  statLabel?: string;
}

export function TrendChart({ values, line, statLabel = "Value" }: Props) {
  const data = values.map((v, i) => ({ game: i + 1, value: v }));
  const allValues = [...values, line];
  const min = Math.floor(Math.min(...allValues) * 0.85);
  const max = Math.ceil(Math.max(...allValues) * 1.1);

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="game"
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[min, max]}
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceLine
            y={line}
            stroke="var(--color-text-muted)"
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{
              value: `Line ${line}`,
              position: "right",
              fontSize: 10,
              fill: "var(--color-text-muted)",
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "0.75rem",
              fontSize: "0.75rem",
            }}
            formatter={(v: any) => [Number(v).toFixed(1), statLabel]}
            labelFormatter={(l: any) => `Game ${l}`}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--color-accent)"
            strokeWidth={2}
            fill="url(#trendGradient)"
            dot={{ r: 3, fill: "var(--color-accent)", strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
