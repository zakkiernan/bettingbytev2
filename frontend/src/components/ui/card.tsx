import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[1.25rem] border border-[color:var(--border-default)] bg-[color:var(--bg-surface)]/95 p-5 backdrop-blur-sm transition-colors hover:border-[color:var(--border-hover)] hover:bg-[color:var(--bg-surface-alt)]/90",
        className,
      )}
      {...props}
    />
  );
}
