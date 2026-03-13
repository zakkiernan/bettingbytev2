import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--border-focus)] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[color:var(--brand-primary)] text-[color:var(--text-inverse)] hover:bg-[color:var(--brand-primary-hover)]",
        secondary: "border border-[color:var(--brand-muted)] bg-transparent text-[color:var(--brand-subtle)] hover:bg-[color:var(--bg-surface-alt)]",
        ghost: "bg-transparent text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-surface-alt)] hover:text-[color:var(--text-primary)]",
      },
      size: {
        default: "h-11 px-4 py-2",
        sm: "h-9 px-3 text-xs",
        lg: "h-12 px-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, ...props }, ref) => {
  return <button className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />;
});
Button.displayName = "Button";

export { Button, buttonVariants };
