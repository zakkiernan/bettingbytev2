"use client";

import Image from "next/image";
import { useState } from "react";

/**
 * NBA.com CDN headshot URL from a player's NBA Stats API ID.
 * These are stable, publicly-accessible, and require no API key.
 */
function headshotUrl(playerId: string) {
  return `https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`;
}

const sizes = {
  sm: { px: 40, container: "h-10 w-10", text: "text-xs" },
  md: { px: 64, container: "h-16 w-16", text: "text-sm" },
  lg: { px: 120, container: "h-[120px] w-[120px]", text: "text-xl" },
} as const;

interface PlayerAvatarProps {
  playerId: string;
  playerName: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function PlayerAvatar({
  playerId,
  playerName,
  size = "md",
  className = "",
}: PlayerAvatarProps) {
  const [failed, setFailed] = useState(false);

  const { px, container, text } = sizes[size];

  const initials = playerName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  if (failed) {
    return (
      <div
        className={`${container} flex-shrink-0 flex items-center justify-center rounded-full bg-[color:var(--color-surface-elevated)] border border-[color:var(--color-border)] ${className}`}
      >
        <span
          className={`font-mono ${text} font-semibold text-[color:var(--color-text-primary)]`}
        >
          {initials}
        </span>
      </div>
    );
  }

  return (
    <div
      className={`${container} relative flex-shrink-0 overflow-hidden rounded-full bg-[color:var(--color-surface-elevated)] border border-[color:var(--color-border)] ${className}`}
    >
      <Image
        src={headshotUrl(playerId)}
        alt={playerName}
        width={px}
        height={Math.round(px * (760 / 1040))}
        className="h-full w-full object-cover object-top"
        onError={() => setFailed(true)}
        unoptimized
      />
    </div>
  );
}
