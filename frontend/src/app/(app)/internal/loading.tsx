import { Card } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function InternalLoading() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Internal
        </p>
        <h1 className="text-2xl font-bold">Pipeline Monitor</h1>
      </div>

      <section className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Tonight&apos;s slate
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="h-3 w-16" />
                </div>
                <Skeleton className="h-6 w-16 rounded-full" />
              </div>
              <div className="mt-3">
                <Skeleton className="h-3 w-20" />
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Pipeline health
          </p>
          <Skeleton className="h-3 w-16" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="space-y-3">
              <Skeleton className="h-4 w-24" />
              <div className="space-y-2">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-5/6" />
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
