import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { PlayerHeader } from "./_components/PlayerHeader";
import { RotationTrendsSection } from "./_components/RotationTrendsSection";
import { AbsenceSection } from "./_components/AbsenceSection";
import { TrendSection } from "./_components/TrendSection";
import { GameLogSection } from "./_components/GameLogSection";
import { ShotChartSection } from "./_components/ShotChartSection";
import { AdvancedStatsSection } from "./_components/AdvancedStatsSection";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ playerId: string }>;
}

export default async function PlayerPage({ params }: PageProps) {
  const { playerId } = await params;

  return (
    <div className="space-y-6">
      <Link href="/nba/props" className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]">
        <ArrowLeft className="h-4 w-4" /> Back to board
      </Link>

      <Suspense fallback={<Card className="space-y-4"><Skeleton className="h-6 w-48" /><Skeleton className="h-4 w-32" /><div className="grid grid-cols-5 gap-3">{Array.from({length:5}).map((_,i)=><Skeleton key={i} className="h-16" />)}</div></Card>}>
        <PlayerHeader playerId={playerId} />
      </Suspense>

      <Suspense fallback={<div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>}>
        <RotationTrendsSection playerId={playerId} />
      </Suspense>

      <Suspense fallback={<Skeleton className="h-48" />}>
        <AbsenceSection playerId={playerId} />
      </Suspense>

      <Suspense fallback={<Skeleton className="h-48" />}>
        <TrendSection playerId={playerId} />
      </Suspense>

      <Suspense fallback={<Card className="space-y-3"><Skeleton className="h-5 w-32" />{Array.from({length:6}).map((_,i)=><Skeleton key={i} className="h-10" />)}</Card>}>
        <GameLogSection playerId={playerId} />
      </Suspense>

      <Suspense fallback={<div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>}>
        <ShotChartSection playerId={playerId} />
      </Suspense>

      <Suspense fallback={<div className="space-y-6"><Skeleton className="h-64" /><Skeleton className="h-48" /><div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-48" /><Skeleton className="h-48" /></div></div>}>
        <AdvancedStatsSection playerId={playerId} />
      </Suspense>
    </div>
  );
}

