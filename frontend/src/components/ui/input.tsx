import * as React from "react";

import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-xl border border-[color:var(--border-default)] bg-[color:var(--bg-surface-alt)] px-4 py-2 text-sm text-[color:var(--text-primary)] outline-none transition-colors placeholder:text-[color:var(--text-tertiary)] focus:border-[color:var(--border-focus)]",
        className,
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
