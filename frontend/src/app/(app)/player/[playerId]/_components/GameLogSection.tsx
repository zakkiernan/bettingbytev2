import { fetchPlayerGameLog } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { GameLogTable } from "@/components/detail/GameLogTable";

export async function GameLogSection({ playerId }: { playerId: string }) {
  const log = await fetchPlayerGameLog(playerId, 10).catch(() => []);

  return (
    <Card>
      <p className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Recent game log</p>
      <GameLogTable log={log} />
    </Card>
  );
}
