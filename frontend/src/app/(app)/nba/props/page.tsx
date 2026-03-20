import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import BoardSection from "./_components/BoardSection";

export const dynamic = "force-dynamic";

function BoardSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="ml-auto h-4 w-48" />
      <Skeleton className="h-[400px]" />
    </div>
  );
}

export default function PropsPage() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
            Tonight's slate
          </p>
          <h1 className="text-2xl font-bold">Prop Board</h1>
        </div>
      </div>

      {/* Board — streams in after data loads */}
      <Suspense fallback={<BoardSkeleton />}>
        <BoardSection />
      </Suspense>
    </div>
  );
}
