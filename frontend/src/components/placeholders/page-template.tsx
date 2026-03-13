import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function PageTemplate({
  title,
  description,
  eyebrow,
  highlights,
  apiContracts,
}: {
  title: string;
  description: string;
  eyebrow: string;
  highlights: string[];
  apiContracts: string[];
}) {
  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <Card className="overflow-hidden border-[color:var(--border-hover)] bg-[linear-gradient(135deg,rgba(124,92,252,0.18),rgba(0,212,255,0.08)_48%,rgba(11,14,23,0.92)_100%)]">
          <div className="space-y-4">
            <Badge tone="live">{eyebrow}</Badge>
            <div>
              <h2 className="text-3xl font-bold tracking-tight">{title}</h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)] md:text-base">{description}</p>
            </div>
          </div>
        </Card>

        <Card>
          <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">API hooks</p>
          <div className="mt-4 space-y-3">
            {apiContracts.map((contract) => (
              <div key={contract} className="rounded-2xl border border-[color:var(--border-default)] bg-[color:var(--bg-surface-alt)]/70 px-4 py-3 font-mono text-sm text-[color:var(--brand-subtle)]">
                {contract}
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {highlights.map((highlight, index) => (
          <Card key={highlight} className="relative overflow-hidden">
            <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--brand-subtle)] to-transparent" />
            <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">Panel {index + 1}</p>
            <p className="mt-3 text-sm leading-7 text-[color:var(--text-secondary)]">{highlight}</p>
          </Card>
        ))}
      </section>
    </div>
  );
}
