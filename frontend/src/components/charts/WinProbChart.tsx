"use client";

import { useState } from "react";
import type { WinProbPoint } from "@/types/api";
import { cn } from "@/lib/utils";

const CHART_WIDTH = 800;
const CHART_HEIGHT = 300;
const PADDING = { top: 20, right: 20, bottom: 30, left: 50 };
const INNER_W = CHART_WIDTH - PADDING.left - PADDING.right;
const INNER_H = CHART_HEIGHT - PADDING.top - PADDING.bottom;

interface WinProbChartProps {
  points: WinProbPoint[];
  homeTeam?: string;
  awayTeam?: string;
  className?: string;
}

export function WinProbChart({ points, homeTeam = "Home", awayTeam = "Away", className }: WinProbChartProps) {
  const [hovered, setHovered] = useState<WinProbPoint | null>(null);

  if (points.length === 0) {
    return (
      <div className={cn("py-12 text-center text-sm text-[color:var(--color-text-muted)]", className)}>
        No win probability data available
      </div>
    );
  }

  const totalEvents = points.length;
  const x = (i: number) => PADDING.left + (i / Math.max(totalEvents - 1, 1)) * INNER_W;
  const y = (pct: number) => PADDING.top + INNER_H - (pct / 100) * INNER_H;

  // Build path
  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.home_pct).toFixed(1)}`)
    .join(" ");

  // Fill area above/below 50%
  const fillAbove = `${pathD} L ${x(totalEvents - 1).toFixed(1)} ${y(50).toFixed(1)} L ${x(0).toFixed(1)} ${y(50).toFixed(1)} Z`;

  // Find biggest swing
  let maxSwing = 0;
  let swingIdx = 0;
  for (let i = 1; i < points.length; i++) {
    const swing = Math.abs(points[i].home_pct - points[i - 1].home_pct);
    if (swing > maxSwing) {
      maxSwing = swing;
      swingIdx = i;
    }
  }

  // Period markers
  const periodStarts: { idx: number; label: string }[] = [];
  let prevPeriod = 0;
  for (let i = 0; i < points.length; i++) {
    if (points[i].period !== prevPeriod) {
      prevPeriod = points[i].period;
      periodStarts.push({ idx: i, label: `Q${points[i].period}` });
    }
  }

  return (
    <div className={cn("relative", className)}>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Win probability
      </p>
      <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="w-full">
        {/* 50% line */}
        <line
          x1={PADDING.left} y1={y(50)} x2={CHART_WIDTH - PADDING.right} y2={y(50)}
          stroke="var(--color-border)" strokeWidth={1} strokeDasharray="4 3"
        />
        {/* Y-axis labels */}
        {[0, 25, 50, 75, 100].map((v) => (
          <text key={v} x={PADDING.left - 8} y={y(v) + 4} textAnchor="end" fontSize={10} fill="var(--color-text-muted)">
            {v}%
          </text>
        ))}
        {/* Period markers */}
        {periodStarts.map((ps) => (
          <g key={ps.label}>
            <line x1={x(ps.idx)} y1={PADDING.top} x2={x(ps.idx)} y2={CHART_HEIGHT - PADDING.bottom} stroke="var(--color-border)" strokeWidth={0.5} strokeDasharray="2 2" />
            <text x={x(ps.idx) + 4} y={CHART_HEIGHT - 8} fontSize={10} fill="var(--color-text-muted)">{ps.label}</text>
          </g>
        ))}
        {/* Fill */}
        <path d={fillAbove} fill="var(--color-accent)" opacity={0.08} />
        {/* Line */}
        <path d={pathD} fill="none" stroke="var(--color-accent)" strokeWidth={2} />
        {/* Biggest swing marker */}
        {maxSwing > 10 && (
          <circle
            cx={x(swingIdx)} cy={y(points[swingIdx].home_pct)} r={5}
            fill="var(--color-warning)" stroke="white" strokeWidth={1.5}
          />
        )}
        {/* Hover overlay */}
        {points.map((p, i) => (
          <rect
            key={i}
            x={x(i) - INNER_W / totalEvents / 2}
            y={PADDING.top}
            width={INNER_W / totalEvents}
            height={INNER_H}
            fill="transparent"
            onMouseEnter={() => setHovered(p)}
            onMouseLeave={() => setHovered(null)}
          />
        ))}
        {/* Hover crosshair */}
        {hovered && (
          <>
            <circle
              cx={x(points.indexOf(hovered))}
              cy={y(hovered.home_pct)}
              r={4}
              fill="var(--color-accent)"
              stroke="white"
              strokeWidth={2}
            />
          </>
        )}
      </svg>
      {/* Hover tooltip */}
      {hovered && (
        <div className="absolute right-4 top-8 z-10 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-xs shadow-lg">
          <div className="font-semibold">Q{hovered.period} &middot; {hovered.home_pts}-{hovered.visitor_pts}</div>
          <div className="mt-1 text-[color:var(--color-text-secondary)]">
            {homeTeam}: <span className="font-mono font-semibold">{hovered.home_pct.toFixed(1)}%</span>
          </div>
          <div className="text-[color:var(--color-text-secondary)]">
            {awayTeam}: <span className="font-mono font-semibold">{hovered.visitor_pct.toFixed(1)}%</span>
          </div>
          {hovered.description && (
            <div className="mt-1 max-w-48 text-[color:var(--color-text-muted)]">{hovered.description}</div>
          )}
        </div>
      )}
      {/* Legend */}
      <div className="mt-2 flex justify-between text-xs text-[color:var(--color-text-muted)]">
        <span>{awayTeam} favored</span>
        <span>{homeTeam} favored</span>
      </div>
    </div>
  );
}
