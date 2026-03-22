"use client";

import { useState } from "react";
import type { ShotChartShot } from "@/types/api";
import { cn } from "@/lib/utils";

// NBA court dimensions: half court is 50ft wide x 47ft long
// NBA API loc_x ranges roughly -250 to 250, loc_y ranges -50 to ~900
// We map to a 500x470 SVG viewBox

const COURT_WIDTH = 500;
const COURT_HEIGHT = 470;

function courtX(locX: number): number {
  return COURT_WIDTH / 2 + locX / 10 * (COURT_WIDTH / 50);
}

function courtY(locY: number): number {
  return COURT_HEIGHT - (locY / 10 + 5) * (COURT_HEIGHT / 47);
}

function HalfCourtSvg() {
  const stroke = "var(--color-border)";
  const strokeWidth = 1.5;
  return (
    <g>
      {/* Court outline */}
      <rect x={0} y={0} width={COURT_WIDTH} height={COURT_HEIGHT} fill="none" stroke={stroke} strokeWidth={strokeWidth} rx={4} />
      {/* Basket */}
      <circle cx={COURT_WIDTH / 2} cy={COURT_HEIGHT - 42} r={7.5} fill="none" stroke={stroke} strokeWidth={strokeWidth} />
      {/* Backboard */}
      <line x1={COURT_WIDTH / 2 - 30} y1={COURT_HEIGHT - 35} x2={COURT_WIDTH / 2 + 30} y2={COURT_HEIGHT - 35} stroke={stroke} strokeWidth={2} />
      {/* Paint / Key */}
      <rect x={COURT_WIDTH / 2 - 80} y={COURT_HEIGHT - 190} width={160} height={190} fill="none" stroke={stroke} strokeWidth={strokeWidth} rx={2} />
      {/* Free throw circle */}
      <circle cx={COURT_WIDTH / 2} cy={COURT_HEIGHT - 190} r={60} fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeDasharray="6 4" />
      {/* Restricted area */}
      <path d={`M ${COURT_WIDTH / 2 - 40} ${COURT_HEIGHT - 35} A 40 40 0 0 0 ${COURT_WIDTH / 2 + 40} ${COURT_HEIGHT - 35}`} fill="none" stroke={stroke} strokeWidth={strokeWidth} />
      {/* Three-point line */}
      <path
        d={`M 30 ${COURT_HEIGHT} L 30 ${COURT_HEIGHT - 140} A 237.5 237.5 0 0 0 ${COURT_WIDTH - 30} ${COURT_HEIGHT - 140} L ${COURT_WIDTH - 30} ${COURT_HEIGHT}`}
        fill="none" stroke={stroke} strokeWidth={strokeWidth}
      />
    </g>
  );
}

interface ShotChartProps {
  shots: ShotChartShot[];
  className?: string;
  title?: string;
}

export function ShotChart({ shots, className, title }: ShotChartProps) {
  const [hovered, setHovered] = useState<ShotChartShot | null>(null);

  if (shots.length === 0) {
    return (
      <div className={cn("flex items-center justify-center py-12 text-sm text-[color:var(--color-text-muted)]", className)}>
        No shot data available
      </div>
    );
  }

  return (
    <div className={cn("relative", className)}>
      {title && (
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          {title}
        </p>
      )}
      <svg viewBox={`0 0 ${COURT_WIDTH} ${COURT_HEIGHT}`} className="w-full" style={{ maxWidth: 560 }}>
        <HalfCourtSvg />
        {shots.map((shot, i) => {
          const cx = courtX(shot.loc_x);
          const cy = courtY(shot.loc_y);
          if (cx < 0 || cx > COURT_WIDTH || cy < 0 || cy > COURT_HEIGHT) return null;
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={4}
              fill={shot.shot_made ? "var(--color-positive)" : "var(--color-negative)"}
              opacity={0.7}
              stroke={hovered === shot ? "white" : "none"}
              strokeWidth={hovered === shot ? 2 : 0}
              onMouseEnter={() => setHovered(shot)}
              onMouseLeave={() => setHovered(null)}
              className="cursor-pointer transition-opacity"
            />
          );
        })}
      </svg>
      {hovered && (
        <div className="absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-3 py-2 text-xs shadow-lg">
          <span className="font-medium">{hovered.action_type || hovered.shot_type}</span>
          <span className="mx-1.5 text-[color:var(--color-text-muted)]">|</span>
          <span>{hovered.shot_distance != null ? `${hovered.shot_distance}ft` : ""}</span>
          <span className="mx-1.5 text-[color:var(--color-text-muted)]">|</span>
          <span className={hovered.shot_made ? "text-[color:var(--color-positive)]" : "text-[color:var(--color-negative)]"}>
            {hovered.shot_made ? "Made" : "Missed"}
          </span>
          {hovered.period && (
            <>
              <span className="mx-1.5 text-[color:var(--color-text-muted)]">|</span>
              <span>Q{hovered.period}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
