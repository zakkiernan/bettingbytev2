"use client";

import { LineChart, Line, ReferenceLine, ResponsiveContainer } from "recharts";

interface Props {
  values: number[];
  line: number;
}

export function Sparkline({ values, line }: Props) {
  const data = values.map((v, i) => ({ i, v }));
  const allValues = [...values, line];
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const pad = (max - min) * 0.15 || 1;

  return (
    <div className="h-8 w-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <ReferenceLine
            y={line}
            stroke="var(--color-text-muted)"
            strokeDasharray="3 3"
            strokeWidth={1}
          />
          <Line
            type="monotone"
            dataKey="v"
            stroke="var(--color-accent)"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
