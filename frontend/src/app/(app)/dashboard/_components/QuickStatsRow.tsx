import { fetchBoard, fetchGamesToday } from "@/lib/api";
import { Card } from "@/components/ui/card";
import type { PropBoardRow } from "@/types/api";

function StatCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <Card className="text-center">
      <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">{label}</div>
      <div className={`mt-1 font-mono text-2xl font-bold ${accent ? "text-[color:var(--color-accent)]" : ""}`}>
        {value}
      </div>
    </Card>
  );
}

export default async function QuickStatsRow() {
  const [boardRes, games] = await Promise.all([
    fetchBoard().catch(() => ({
      props: [] as PropBoardRow[],
      meta: { total_count: 0, game_count: 0, updated_at: undefined as string | undefined, stat_types_available: [] },
    })),
    fetchGamesToday().catch(() => []),
  ]);

  const totalProps = boardRes.meta.total_count;
  const totalEdges = games.reduce((sum, g) => sum + g.edge_count, 0);
  const gamesWithEdges = games.filter((g) => g.edge_count > 0).length;

  const recommended = boardRes.props.filter((p) => p.recommended_side != null);
  const avgConfidence =
    recommended.length > 0
      ? Math.round(
          (recommended.reduce((sum, p) => sum + p.confidence, 0) / recommended.length) * 100,
        )
      : 0;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard label="Props Analyzed" value={String(totalProps)} />
      <StatCard label="Edges Found" value={String(totalEdges)} accent={totalEdges > 0} />
      <StatCard label="Games w/ Edges" value={`${gamesWithEdges} / ${games.length}`} />
      <StatCard label="Avg Confidence" value={avgConfidence > 0 ? `${avgConfidence}%` : "—"} />
    </div>
  );
}
