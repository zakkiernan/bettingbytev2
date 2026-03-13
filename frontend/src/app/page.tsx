import Link from "next/link";
import { ArrowRight, Radar, ShieldCheck, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const valueProps = [
  {
    title: "Transparent models",
    body: "Pregame points surfaces explainable levers first so every downstream feature inherits trust.",
    icon: ShieldCheck,
  },
  {
    title: "Timed line snapshots",
    body: "Scheduled early, late, and tip captures create the historical pricing backbone edge analysis needs.",
    icon: Radar,
  },
  {
    title: "Dark trading shell",
    body: "The frontend skeleton is ready for dashboard, prop board, live center, picks, community, and settings work.",
    icon: Sparkles,
  },
] as const;

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(124,92,252,0.24),_transparent_32%),linear-gradient(180deg,_#0b0e17_0%,_#121629_40%,_#0b0e17_100%)] px-4 py-10 text-[color:var(--text-primary)] md:px-8">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="grid gap-6 rounded-[2rem] border border-[color:var(--border-default)] bg-[color:var(--bg-surface)]/75 p-8 backdrop-blur md:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.8fr)] md:p-10">
          <div className="space-y-5">
            <p className="text-xs uppercase tracking-[0.24em] text-[color:var(--brand-subtle)]">BettingByte v2</p>
            <h1 className="max-w-3xl text-4xl font-bold tracking-tight md:text-6xl">Backend-first betting intelligence with a frontend ready to meet it.</h1>
            <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)] md:text-base">
              This scaffold ships the navigation shell, dark theme, auth handoff, and route map the frontend team can build against while backend workstreams keep moving.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard">
                <Button>
                  Open dashboard
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/login">
                <Button variant="secondary">Try login flow</Button>
              </Link>
            </div>
          </div>

          <Card className="border-[color:var(--border-hover)] bg-[color:var(--bg-surface-alt)]/70">
            <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">Initial routes</p>
            <div className="mt-4 grid gap-3 text-sm text-[color:var(--text-secondary)]">
              <div>/dashboard</div>
              <div>/props and /props/[signalId]</div>
              <div>/player/[playerId]</div>
              <div>/live and /live/[gameId]</div>
              <div>/picks, /community, /settings</div>
            </div>
          </Card>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {valueProps.map(({ title, body, icon: Icon }) => (
            <Card key={title}>
              <div className="flex items-center gap-3 text-[color:var(--brand-subtle)]">
                <Icon className="h-5 w-5" />
                <h2 className="font-semibold text-[color:var(--text-primary)]">{title}</h2>
              </div>
              <p className="mt-4 text-sm leading-7 text-[color:var(--text-secondary)]">{body}</p>
            </Card>
          ))}
        </section>
      </div>
    </main>
  );
}
