import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)] px-4 py-2 text-sm text-[color:var(--color-text-primary)] outline-none transition-colors placeholder:text-[color:var(--color-text-muted)] focus:border-[color:var(--color-accent)]",
        className,
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
