import { fetchBoard, fetchGamesToday } from "@/lib/api";
import { PropTable } from "@/components/board/PropTable";

export default async function BoardSection() {
  const [boardRes, games] = await Promise.all([
    fetchBoard().catch(() => ({
      props: [] as never[],
      meta: { total_count: 0, game_count: 0, updated_at: undefined as string | undefined, stat_types_available: ["points"] },
    })),
    fetchGamesToday().catch(() => []),
  ]);

  const lastUpdated = boardRes.meta.updated_at
    ? new Date(boardRes.meta.updated_at).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        timeZone: "America/New_York",
      })
    : null;

  return (
    <>
      <div className="text-right text-xs text-[color:var(--color-text-muted)]">
        {boardRes.meta.total_count > 0 ? (
          <>
            <span className="font-mono">{boardRes.meta.total_count}</span> props
            across{" "}
            <span className="font-mono">{boardRes.meta.game_count}</span> games
            {lastUpdated && <> · last run {lastUpdated}</>}
          </>
        ) : (
          "No signals yet — run the model to populate the board."
        )}
      </div>

      <PropTable initialProps={boardRes.props} games={games} statTypes={boardRes.meta.stat_types_available} />
    </>
  );
}
