import { Card } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function PlayerLoading() {
  return (
    <div className="space-y-6">
      {/* Back link */}
      <Skeleton className="h-4 w-28" />

      {/* Profile header */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-36" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>

        {/* Stats grid */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 text-center"
            >
              <Skeleton className="mx-auto h-3 w-10" />
              <Skeleton className="mx-auto mt-2 h-7 w-12" />
            </div>
          ))}
        </div>
      </Card>

      {/* Rotation + Scoring profile */}
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} className="space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-40 w-full rounded-2xl" />
          </Card>
        ))}
      </div>

      {/* Active props + Trend */}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <Skeleton className="mb-4 h-3 w-36" />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-2">
                    <Skeleton className="h-5 w-24" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <div className="flex gap-4">
                    <Skeleton className="h-8 w-12" />
                    <Skeleton className="h-8 w-12" />
                    <Skeleton className="h-8 w-12" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <Skeleton className="mb-4 h-3 w-32" />
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3 text-center"
              >
                <Skeleton className="mx-auto h-3 w-16" />
                <Skeleton className="mx-auto mt-2 h-7 w-12" />
              </div>
            ))}
          </div>
          <div className="mt-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </Card>
      </div>

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
