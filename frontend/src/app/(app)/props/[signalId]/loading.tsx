import { Card } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function PropDetailLoading() {
  return (
    <div className="space-y-6">
      {/* Back link + profile link */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-9 w-36 rounded-xl" />
      </div>

      {/* The Verdict */}
      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Skeleton className="h-7 w-40" />
              <Skeleton className="h-5 w-10" />
              <Skeleton className="h-6 w-16 rounded-full" />
              <Skeleton className="h-6 w-14 rounded-full" />
            </div>
            <Skeleton className="h-4 w-36" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>

        {/* Summary stats */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/60 px-4 py-3 text-center"
            >
              <Skeleton className="mx-auto h-3 w-16" />
              <Skeleton className="mx-auto mt-2 h-7 w-14" />
            </div>
          ))}
        </div>

        {/* Market view + Model note */}
        <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-4 py-4 space-y-3">
            <Skeleton className="h-3 w-20" />
            <div className="grid gap-3 sm:grid-cols-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-[color:var(--color-border)] p-3 space-y-2">
                  <Skeleton className="h-3 w-12" />
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-3 w-20" />
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-4 py-4 space-y-3">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </Card>

      {/* Chart area */}
      <Card>
        <Skeleton className="mb-4 h-3 w-40" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </Card>

      {/* Game log */}
      <Card>
        <Skeleton className="mb-4 h-3 w-28" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </Card>
    </div>
  );
}
