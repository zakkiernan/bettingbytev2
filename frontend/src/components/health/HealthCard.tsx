import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

interface Props {
  title: string;
  rows: { label: string; value: ReactNode; warn?: boolean }[];
}

export function HealthCard({ title, rows }: Props) {
  return (
    <Card>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        {title}
      </p>
      <div className="space-y-2">
        {rows.map(({ label, value, warn }) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-sm text-[color:var(--color-text-secondary)]">
              {label}
            </span>
            <span
              className={`font-mono text-sm font-semibold ${
                warn
                  ? "text-[color:var(--color-warning)]"
                  : "text-[color:var(--color-text-primary)]"
              }`}
            >
              {value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
