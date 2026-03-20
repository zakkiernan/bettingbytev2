import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import SlateSection from "./_components/SlateSection";
import HealthSection from "./_components/HealthSection";

export const dynamic = "force-dynamic";

function SlateSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[88px]" />
      ))}
    </div>
  );
}

function HealthSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-[160px]" />
      ))}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Internal
        </p>
        <h1 className="text-2xl font-bold">Dashboard</h1>
      </div>

      {/* Tonight's slate summary */}
      <section className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Tonight's slate
        </p>
        <Suspense fallback={<SlateSkeleton />}>
          <SlateSection />
        </Suspense>
      </section>

      {/* Pipeline health */}
      <section className="space-y-3">
        <Suspense fallback={<HealthSkeleton />}>
          <HealthSection />
        </Suspense>
      </section>
    </div>
  );
}
