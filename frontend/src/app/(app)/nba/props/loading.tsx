function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function PropsLoading() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Tonight&apos;s slate
          </p>
          <h1 className="text-2xl font-bold">Prop Board</h1>
        </div>
        <Skeleton className="h-3 w-48" />
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-20 rounded-full" />
        ))}
      </div>

      {/* Prop rows */}
      <div className="space-y-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-4 rounded-2xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)]/95 px-5 py-4"
          >
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-12 ml-auto" />
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-6 w-14 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
