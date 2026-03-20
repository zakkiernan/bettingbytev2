import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const toneClasses = {
  default: "border-[color:var(--color-border)] text-[color:var(--color-text-secondary)]",
  success: "border-[color:var(--color-positive)]/40 bg-[color:var(--color-positive)]/10 text-[color:var(--color-positive)]",
  danger: "border-[color:var(--color-negative)]/40 bg-[color:var(--color-negative)]/10 text-[color:var(--color-negative)]",
  live: "border-[color:var(--color-accent)]/40 bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]",
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
