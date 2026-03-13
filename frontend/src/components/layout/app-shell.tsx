import type { ReactNode } from "react";

import Link from "next/link";
import { Bolt, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { dashboardMetrics, primaryNavigation, quickLinks } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(124,92,252,0.18),_transparent_28%),linear-gradient(180deg,_#0b0e17_0%,_#0f1320_45%,_#0b0e17_100%)] text-[color:var(--text-primary)]">
      <div className="mx-auto grid min-h-screen max-w-[1500px] grid-cols-1 md:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="hidden border-r border-[color:var(--border-default)]/70 bg-[color:var(--bg-surface)]/70 p-6 backdrop-blur md:flex md:flex-col">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[color:var(--brand-glow)] text-[color:var(--brand-subtle)]">
              <Bolt className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">BettingByte</p>
              <p className="font-semibold">Data Terminal</p>
            </div>
          </div>

          <nav className="space-y-2">
            {primaryNavigation.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 text-sm text-[color:var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[color:var(--bg-surface-alt)] hover:text-[color:var(--text-primary)]",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          <div className="mt-8 space-y-4 rounded-[1.5rem] border border-[color:var(--border-default)] bg-[color:var(--bg-surface-alt)]/70 p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Quick Links</p>
              <Badge tone="live">Build</Badge>
            </div>
            <div className="space-y-2">
              {quickLinks.map((link) => (
                <Link key={link.href} href={link.href} className="flex items-center justify-between rounded-xl px-3 py-2 text-sm text-[color:var(--text-secondary)] transition-colors hover:bg-[color:var(--bg-surface)] hover:text-[color:var(--text-primary)]">
                  <span>{link.label}</span>
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ))}
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-20 border-b border-[color:var(--border-default)]/70 bg-[color:var(--bg-base)]/90 px-4 py-4 backdrop-blur md:px-8">
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">NBA points only</p>
                  <h1 className="text-xl font-semibold md:text-2xl">BettingByte v2 frontend shell</h1>
                </div>
                <Badge>Dark-first</Badge>
              </div>

              <div className="grid grid-cols-3 gap-3 overflow-x-auto md:max-w-xl">
                {dashboardMetrics.map(({ label, value, icon: Icon }) => (
                  <div key={label} className="rounded-2xl border border-[color:var(--border-default)] bg-[color:var(--bg-surface)]/70 p-3">
                    <div className="flex items-center justify-between text-[color:var(--text-secondary)]">
                      <span className="text-xs uppercase tracking-[0.18em]">{label}</span>
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-2 font-mono text-2xl font-bold text-[color:var(--text-primary)]">{value}</p>
                  </div>
                ))}
              </div>

              <div className="flex gap-2 overflow-x-auto md:hidden">
                {primaryNavigation.map(({ href, label }) => (
                  <Link key={href} href={href} className="rounded-full border border-[color:var(--border-default)] bg-[color:var(--bg-surface)] px-3 py-2 text-sm text-[color:var(--text-secondary)] transition-colors hover:text-[color:var(--text-primary)]">
                    {label}
                  </Link>
                ))}
              </div>
            </div>
          </header>

          <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
