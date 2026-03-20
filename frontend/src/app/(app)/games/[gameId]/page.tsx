import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { fetchGameDetail } from "@/lib/api";
import { GameContextSection } from "./_components/GameContextSection";
import { GamePropsSection } from "./_components/GamePropsSection";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ gameId: string }>;
}

export default async function GameDetailPage({ params }: PageProps) {
  const { gameId } = await params;

  const game = await fetchGameDetail(gameId).catch(() => null);

  if (!game) {
    return (
      <div className="space-y-4">
        <Link
          href="/games"
          className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to games
        </Link>
        <p className="py-20 text-center text-[color:var(--color-text-secondary)]">Game not found.</p>
      </div>
    );
  }

  const gameTime = game.game_time_utc
    ? new Date(game.game_time_utc).toLocaleString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/New_York",
      })
    : null;

  return (
    <div className="space-y-6">
      <Link
        href="/games"
        className="inline-flex items-center gap-2 text-sm text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)]"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to games
      </Link>

      {/* Matchup header - renders immediately */}
      <Card className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">
              {game.away_team.abbreviation}{" "}
              <span className="text-[color:var(--color-text-muted)]">@</span>{" "}
              {game.home_team.abbreviation}
            </h1>
            <p className="text-sm text-[color:var(--color-text-secondary)]">
              {game.away_team.full_name} vs {game.home_team.full_name}
            </p>
          </div>
          <div className="text-right text-sm text-[color:var(--color-text-muted)]">
            {gameTime && <p>{gameTime}</p>}
          </div>
        </div>
      </Card>

      {/* Lineup & defense context - streams in */}
      <Suspense fallback={
        <div className="space-y-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-48" />
        </div>
      }>
        <GameContextSection gameId={gameId} />
      </Suspense>

      {/* Game props - streams in */}
      <Suspense fallback={
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-96" />
        </div>
      }>
        <GamePropsSection gameId={gameId} />
      </Suspense>
    </div>
  );
}
