function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function DashboardLoading() {
  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>

      {/* Top Picks */}
      <section className="space-y-3">
        <Skeleton className="h-3 w-20" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[280px]" />
          ))}
        </div>
      </section>

      {/* Games */}
      <section className="space-y-3">
        <Skeleton className="h-3 w-28" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[80px]" />
          ))}
        </div>
      </section>

      {/* Stats */}
      <section className="space-y-3">
        <Skeleton className="h-3 w-20" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[72px]" />
          ))}
        </div>
      </section>
    </div>
  );
}
