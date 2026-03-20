import { Card } from "@/components/ui/card";

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-[color:var(--color-surface-elevated)] ${className ?? ""}`} />;
}

export default function GamesLoading() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          Tonight&apos;s slate
        </p>
        <h1 className="text-2xl font-bold">Games</h1>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i}>
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-2">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-44" />
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
            <div className="mt-3 flex gap-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-16" />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
