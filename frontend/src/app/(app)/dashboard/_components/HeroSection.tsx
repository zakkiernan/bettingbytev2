import Link from "next/link";
import { fetchBoard, fetchGamesToday, fetchLiveGames } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import type { PropBoardRow } from "@/types/api";

function getEdgeSummary(prop: PropBoardRow): { side: "OVER" | "UNDER"; edge: number } {
  if (prop.recommended_side === "UNDER") {
    return { side: "UNDER", edge: Math.abs(prop.edge_under) };
  }

  if (prop.recommended_side === "OVER") {
    return { side: "OVER", edge: Math.abs(prop.edge_over) };
  }

  if (Math.abs(prop.edge_over) >= Math.abs(prop.edge_under)) {
    return { side: "OVER", edge: Math.abs(prop.edge_over) };
  }

  return { side: "UNDER", edge: Math.abs(prop.edge_under) };
}

export default async function HeroSection() {
  const [games, liveGames, board] = await Promise.all([
    fetchGamesToday().catch(() => []),
    fetchLiveGames().catch(() => []),
    fetchBoard().catch(() => ({
      props: [] as PropBoardRow[],
      meta: {
        total_count: 0,
        game_count: 0,
        updated_at: undefined as string | undefined,
        stat_types_available: [],
      },
    })),
  ]);

  const recommendedProps = board.props.filter((prop) => prop.recommended_side);
  const topEdgePool = recommendedProps.length > 0 ? recommendedProps : board.props;
  const rankedProps = topEdgePool
    .map((prop) => ({ prop, summary: getEdgeSummary(prop) }))
    .sort((a, b) => b.summary.edge - a.summary.edge || b.prop.confidence - a.prop.confidence);
  const topEdge = rankedProps[0] ?? null;

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">Tonight&apos;s Edge</h1>
        {liveGames.length > 0 && (
          <Link href="/nba/live">
            <Badge tone="live" className="gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--color-accent)] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[color:var(--color-accent)]" />
              </span>
              {liveGames.length} {liveGames.length === 1 ? "game" : "games"} live
            </Badge>
          </Link>
        )}
      </div>
      <p className="text-sm text-[color:var(--color-text-secondary)]">
        {dateStr}
        {games.length > 0 && (
          <>
            {" "}&middot;{" "}
            <span className="font-mono font-semibold text-[color:var(--color-text-primary)]">
              {games.length}
            </span>{" "}
            NBA {games.length === 1 ? "game" : "games"}
          </>
        )}
      </p>
      <p className="text-sm text-[color:var(--color-text-secondary)]">
        {topEdge
          ? `Top edge: ${topEdge.prop.player_name} ${topEdge.prop.stat_type} ${topEdge.summary.side} by ${topEdge.summary.edge.toFixed(1)} (${Math.round(topEdge.prop.confidence * 100)}% confidence)`
          : "Top edge will appear once the board has live signals."}
      </p>
    </div>
  );
}
