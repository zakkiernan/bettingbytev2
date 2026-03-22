import type { GameLogEntry } from "@/types/api";

interface Props {
  log: GameLogEntry[];
  line?: number;
  highlightStat?: string;
}

const defaultStatAccessor = (row: GameLogEntry) => row.points;

const statAccessor: Record<string, (row: GameLogEntry) => number> = {
  points: defaultStatAccessor,
  rebounds: (row) => row.rebounds,
  assists: (row) => row.assists,
  steals: (row) => row.steals,
  blocks: (row) => row.blocks,
  threes_made: (row) => row.threes_made,
  threes: (row) => row.threes_made,
};

export function GameLogTable({ log, line, highlightStat = "points" }: Props) {
  if (log.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-[color:var(--color-text-muted)]">
        No game log available.
      </p>
    );
  }

  const accessor = statAccessor[highlightStat] ?? defaultStatAccessor;
  const showThrees = highlightStat === "threes_made" || highlightStat === "threes";

  const hits = line != null ? log.filter((row) => accessor(row) > line).length : null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[color:var(--color-border)] text-left text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
            <th className="pb-2 pr-4">Date</th>
            <th className="pb-2 pr-4">Opp</th>
            <th className="pb-2 pr-4 text-right">MIN</th>
            <th className={`pb-2 pr-4 text-right ${highlightStat === "points" ? "font-bold" : ""}`}>PTS</th>
            <th className={`pb-2 pr-4 text-right ${highlightStat === "rebounds" ? "font-bold" : ""}`}>REB</th>
            <th className={`pb-2 pr-4 text-right ${highlightStat === "assists" ? "font-bold" : ""}`}>AST</th>
            {showThrees && <th className="pb-2 pr-4 text-right font-bold">3PM</th>}
            <th className="pb-2 text-right">+/-</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[color:var(--color-border)]">
          {log.map((row) => {
            const dateStr = row.game_date
              ? new Date(row.game_date).toLocaleDateString("en-US", {
                  month: "numeric",
                  day: "numeric",
                })
              : "--";
            const highlighted = accessor(row);
            const hitLine = line != null ? highlighted > line : null;

            return (
              <tr
                key={row.game_id}
                className="transition-colors hover:bg-[color:var(--color-surface-elevated)]/40"
              >
                <td className="py-2 pr-4 text-[color:var(--color-text-secondary)]">
                  {dateStr}
                </td>
                <td className="py-2 pr-4">
                  <span className="text-[color:var(--color-text-secondary)]">
                    {row.is_home ? "vs" : "@"}
                  </span>{" "}
                  {row.opponent}
                </td>
                <td className="py-2 pr-4 text-right font-mono text-[color:var(--color-text-secondary)]">
                  {row.minutes.toFixed(0)}
                </td>
                <StatCell
                  value={row.points}
                  isHighlighted={highlightStat === "points"}
                  hitLine={highlightStat === "points" ? hitLine : null}
                  line={highlightStat === "points" ? line : undefined}
                />
                <StatCell
                  value={row.rebounds}
                  isHighlighted={highlightStat === "rebounds"}
                  hitLine={highlightStat === "rebounds" ? hitLine : null}
                  line={highlightStat === "rebounds" ? line : undefined}
                />
                <StatCell
                  value={row.assists}
                  isHighlighted={highlightStat === "assists"}
                  hitLine={highlightStat === "assists" ? hitLine : null}
                  line={highlightStat === "assists" ? line : undefined}
                />
                {showThrees && (
                  <StatCell
                    value={row.threes_made}
                    isHighlighted
                    hitLine={hitLine}
                    line={line}
                  />
                )}
                <td
                  className={`py-2 text-right font-mono ${
                    row.plus_minus >= 0
                      ? "text-[color:var(--color-positive)]"
                      : "text-[color:var(--color-negative)]"
                  }`}
                >
                  {row.plus_minus >= 0 ? "+" : ""}
                  {row.plus_minus.toFixed(0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {line != null && (
        <p className="mt-2 text-xs text-[color:var(--color-text-muted)]">
          {highlightStat.toUpperCase()} colored green/red vs tonight&apos;s line of {line}. Last {log.length}: {hits}/{log.length} overs.
        </p>
      )}
    </div>
  );
}

function StatCell({
  value,
  isHighlighted,
  hitLine,
  line,
}: {
  value: number;
  isHighlighted: boolean;
  hitLine: boolean | null;
  line?: number;
}) {
  return (
    <td className={`py-2 pr-4 text-right font-mono ${isHighlighted ? "font-bold" : "text-[color:var(--color-text-secondary)]"}`}>
      <span
        className={
          isHighlighted && hitLine === true
            ? "text-[color:var(--color-positive)]"
            : isHighlighted && hitLine === false
              ? "text-[color:var(--color-negative)]"
              : ""
        }
      >
        {value.toFixed(0)}
      </span>
      {isHighlighted && line != null && (
        <span className="ml-1 text-xs text-[color:var(--color-text-muted)]">
          {hitLine ? "hit" : "miss"}
        </span>
      )}
    </td>
  );
}