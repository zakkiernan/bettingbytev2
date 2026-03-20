import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import GamesGrid from "./_components/GamesGrid";

export const dynamic = "force-dynamic";

function GamesGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[120px]" />
      ))}
    </div>
  );
}

export default function GamesPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Tonight's slate
        </p>
        <h1 className="text-2xl font-bold">Games</h1>
      </div>

      <Suspense fallback={<GamesGridSkeleton />}>
        <GamesGrid />
      </Suspense>
    </div>
  );
}
