import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { PropDetailContent } from "./_components/PropDetailContent";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ signalId: string }>;
}

export default async function PropDetailPage({ params }: PageProps) {
  const { signalId } = await params;
  const id = parseInt(signalId, 10);

  if (isNaN(id)) {
    return (
      <div className="py-20 text-center text-[color:var(--color-text-secondary)]">
        Invalid signal ID.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href="/props"
        className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to board
      </Link>

      <Suspense fallback={
        <div className="space-y-6">
          <Card className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-4 w-32" />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {Array.from({length:5}).map((_,i)=><Skeleton key={i} className="h-20" />)}
            </div>
            <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
          </Card>
          <Skeleton className="h-48" />
          <Skeleton className="h-64" />
        </div>
      }>
        <PropDetailContent signalId={id} />
      </Suspense>
    </div>
  );
}
