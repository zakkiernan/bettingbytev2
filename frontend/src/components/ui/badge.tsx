import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const toneClasses = {
  default: "border-[color:var(--border-default)] text-[color:var(--text-secondary)]",
  success: "border-[color:var(--edge-positive)]/40 bg-[color:var(--edge-positive)]/10 text-[color:var(--edge-positive)]",
  danger: "border-[color:var(--edge-negative)]/40 bg-[color:var(--edge-negative)]/10 text-[color:var(--edge-negative)]",
  live: "border-[color:var(--live-accent)]/40 bg-[color:var(--live-accent)]/10 text-[color:var(--live-accent)]",
} as const;

type BadgeTone = keyof typeof toneClasses;

export function Badge({ className, tone = "default", ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em]",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}
