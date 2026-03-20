import { Card } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function GameDetailLoading() {
  return (
    <div className="space-y-6">
      {/* Back link */}
      <Skeleton className="h-4 w-28" />

      {/* Matchup header */}
      <Card className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <Skeleton className="h-7 w-40" />
            <Skeleton className="h-4 w-56" />
          </div>
          <div className="space-y-2 text-right">
            <Skeleton className="h-4 w-32 ml-auto" />
            <Skeleton className="h-4 w-24 ml-auto" />
          </div>
        </div>
      </Card>

      {/* Lineup & injuries section */}
      <div>
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Lineup &amp; injuries
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Card key={i} className="space-y-3">
              <Skeleton className="h-5 w-20" />
              {Array.from({ length: 5 }).map((_, j) => (
                <div key={j} className="flex items-center justify-between">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </Card>
          ))}
        </div>
      </div>

      {/* Defense comparison */}
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} className="space-y-3">
            <Skeleton className="h-4 w-28" />
            <div className="grid gap-2 sm:grid-cols-3">
              {Array.from({ length: 3 }).map((_, j) => (
                <div key={j} className="rounded-xl border border-[color:var(--color-border)] p-3 text-center">
                  <Skeleton className="mx-auto h-3 w-12" />
                  <Skeleton className="mx-auto mt-2 h-6 w-10" />
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      {/* Game props */}
      <div>
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Game props
        </p>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-4 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/95 px-5 py-4"
            >
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-12 ml-auto" />
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-6 w-14 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
