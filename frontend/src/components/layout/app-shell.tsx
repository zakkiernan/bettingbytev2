import type { ReactNode } from "react";
import { Suspense } from "react";
import Link from "next/link";
import { Bolt, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { fetchGamesToday, fetchHealth } from "@/lib/api";
import { internalNavigation, primaryNavigation, quickLinks, sportsNavigation } from "@/lib/navigation";
import { cn } from "@/lib/utils";

async function HeaderMetrics() {
  try {
    const [health, games] = await Promise.all([fetchHealth(), fetchGamesToday()]);

    const totalEdges = games.reduce((sum, g) => sum + g.edge_count, 0);
    const stale = health.lines.stale_captures;

    return (
      <div className="flex items-center gap-4">
        <MetricPill label="Games" value={String(games.length)} />
        <MetricPill label="Props" value={String(health.lines.tonight_prop_count)} />
        <MetricPill
          label={stale > 0 ? "Stale" : "Edges"}
          value={String(stale > 0 ? stale : totalEdges)}
          warn={stale > 0}
        />
      </div>
    );
  } catch {
    return (
      <div className="rounded-lg border border-[color:var(--color-warning)]/30 bg-[color:var(--color-warning-muted)] px-3 py-1.5">
        <p className="text-xs text-[color:var(--color-warning)]">API offline</p>
      </div>
    );
  }
}

function MetricPill({
  label,
  value,
  warn,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[color:var(--color-text-muted)]">{label}</span>
      <span
        className={cn(
          "font-mono text-sm font-semibold",
          warn ? "text-[color:var(--color-warning)]" : "text-[color:var(--color-text-primary)]",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function SportSelector() {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">Sport</span>
      <div className="flex items-center gap-1 rounded-lg border border-[color:var(--color-border-subtle)] bg-[color:var(--color-surface)] p-1">
        {sportsNavigation.map((sport) =>
          sport.enabled ? (
            <Link
              key={sport.key}
              href={sport.href}
              className="rounded-md bg-[color:var(--color-accent-muted)] px-2.5 py-1 text-xs font-medium text-[color:var(--color-accent)]"
            >
              {sport.label}
            </Link>
          ) : (
            <span
              key={sport.key}
              className="rounded-md px-2.5 py-1 text-xs font-medium text-[color:var(--color-text-muted)]"
            >
              {sport.label}
            </span>
          ),
        )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[color:var(--color-background)] text-[color:var(--color-text-primary)]">
      <div className="mx-auto grid min-h-screen max-w-[1440px] grid-cols-1 md:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="hidden border-r border-[color:var(--color-border-subtle)] bg-[color:var(--color-surface)] md:flex md:flex-col">
          <div className="flex items-center gap-3 border-b border-[color:var(--color-border-subtle)] px-5 py-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[color:var(--color-accent-muted)] text-[color:var(--color-accent)]">
              <Bolt className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold">BettingByte</p>
            </div>
          </div>

          <div className="px-3 py-3">
            <SportSelector />
          </div>

          <nav className="flex-1 space-y-0.5 px-3 py-3">
            {primaryNavigation.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-[color:var(--color-text-secondary)] transition-colors hover:bg-[color:var(--color-surface-elevated)] hover:text-[color:var(--color-text-primary)]"
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          <div className="mx-3 mb-3 space-y-2 rounded-lg border border-[color:var(--color-border-subtle)] p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-[color:var(--color-text-muted)]">Quick Links</p>
            </div>
            {quickLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs text-[color:var(--color-text-secondary)] transition-colors hover:bg-[color:var(--color-surface-elevated)] hover:text-[color:var(--color-text-primary)]"
              >
                <span>{link.label}</span>
                <ChevronRight className="h-3 w-3" />
              </Link>
            ))}
          </div>

          {/* Internal tools */}
          <div className="mx-3 mb-3 border-t border-[color:var(--color-border-subtle)] pt-3">
            {internalNavigation.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[color:var(--color-text-muted)] transition-colors hover:bg-[color:var(--color-surface-elevated)] hover:text-[color:var(--color-text-secondary)]"
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{label}</span>
                <Badge className="ml-auto scale-90">Internal</Badge>
              </Link>
            ))}
          </div>
        </aside>

        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[color:var(--color-border-subtle)] bg-[color:var(--color-background)]/95 px-4 py-3 backdrop-blur-sm md:px-6">
            <div className="flex items-center gap-4">
              <h1 className="text-sm font-semibold">BettingByte</h1>
            </div>

            <div className="flex items-center gap-4">
              <SportSelector />
              <Suspense
                fallback={
                  <div className="flex items-center gap-4">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="h-4 w-16 animate-pulse rounded bg-[color:var(--color-surface-elevated)]" />
                    ))}
                  </div>
                }
              >
                <HeaderMetrics />
              </Suspense>
            </div>
          </header>

          <div className="flex gap-1 overflow-x-auto border-b border-[color:var(--color-border-subtle)] px-4 md:hidden">
            {primaryNavigation.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="whitespace-nowrap px-3 py-2.5 text-sm text-[color:var(--color-text-secondary)] transition-colors hover:text-[color:var(--color-text-primary)]"
              >
                {label}
              </Link>
            ))}
          </div>

          <main className="flex-1 px-4 py-6 md:px-6 md:py-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
