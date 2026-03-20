import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import HeroSection from "./_components/HeroSection";
import TopPicksSection from "./_components/TopPicksSection";
import LiveGamesStrip from "./_components/LiveGamesStrip";
import TonightGamesSection from "./_components/TonightGamesSection";
import QuickStatsRow from "./_components/QuickStatsRow";

export const dynamic = "force-dynamic";

function HeroSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-64" />
    </div>
  );
}

function PicksSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-[280px]" />
      ))}
    </div>
  );
}

function LiveStripSkeleton() {
  return (
    <div className="flex gap-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] w-[260px] flex-shrink-0" />
      ))}
    </div>
  );
}

function GamesSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[80px]" />
      ))}
    </div>
  );
}

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[72px]" />
      ))}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <Suspense fallback={<HeroSkeleton />}>
        <HeroSection />
      </Suspense>

      {/* Top Picks */}
      <section className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Top picks
        </p>
        <Suspense fallback={<PicksSkeleton />}>
          <TopPicksSection />
        </Suspense>
      </section>

      {/* Live Games — only renders content if games are active */}
      <section className="space-y-3">
        <Suspense fallback={<LiveStripSkeleton />}>
          <LiveGamesStrip />
        </Suspense>
      </section>

      {/* Tonight's Games */}
      <section className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Tonight&apos;s games
        </p>
        <Suspense fallback={<GamesSkeleton />}>
          <TonightGamesSection />
        </Suspense>
      </section>

      {/* Quick Stats */}
      <section className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          At a glance
        </p>
        <Suspense fallback={<StatsSkeleton />}>
          <QuickStatsRow />
        </Suspense>
      </section>
    </div>
  );
}
