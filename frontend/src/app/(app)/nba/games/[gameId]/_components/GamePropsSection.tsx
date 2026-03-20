import { fetchBoard, fetchGamesToday } from "@/lib/api";
import { PropTable } from "@/components/board/PropTable";
import type { PropBoardRow } from "@/types/api";

export async function GamePropsSection({ gameId }: { gameId: string }) {
  const [boardRes, games] = await Promise.all([
    fetchBoard({ game_id: gameId }).catch(() => ({
      props: [] as PropBoardRow[],
      meta: { total_count: 0, game_count: 0, stat_types_available: ["points"] },
    })),
    fetchGamesToday().catch(() => []),
  ]);

  return (
    <div>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Game props ({boardRes.props.length})
      </p>
      <PropTable
        initialProps={boardRes.props}
        games={games}
        statTypes={boardRes.meta.stat_types_available}
      />
    </div>
  );
}
