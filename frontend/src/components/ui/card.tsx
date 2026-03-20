import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[1.25rem] border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/95 p-5 backdrop-blur-sm transition-colors hover:border-[color:var(--color-border)] hover:bg-[color:var(--color-surface-elevated)]/90",
        className,
      )}
      {...props}
    />
  );
}
