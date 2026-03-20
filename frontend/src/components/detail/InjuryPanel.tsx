import { Badge } from "@/components/ui/badge";
import type { InjuryEntry } from "@/types/api";

const STATUS_TONE: Record<
  string,
  "danger" | "live" | "default" | "success"
> = {
  Out: "danger",
  Doubtful: "danger",
  Questionable: "live",
  Probable: "default",
};

interface Props {
  entries: InjuryEntry[];
  teamAbbr: string;
}

export function InjuryPanel({ entries, teamAbbr }: Props) {
  if (entries.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-[color:var(--color-text-muted)]">
        No players listed on official report for {teamAbbr}.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <div
          key={entry.player_name}
          className="flex items-start justify-between gap-4 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/50 px-4 py-3"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="font-medium">{entry.player_name}</div>
              {entry.team_abbreviation !== teamAbbr && (
                <span className="text-xs text-[color:var(--color-text-muted)]">
                  {entry.team_abbreviation}
                </span>
              )}
            </div>
            {entry.reason && (
              <div className="mt-0.5 max-w-[360px] text-xs text-[color:var(--color-text-muted)]">
                {entry.reason}
              </div>
            )}
          </div>
          <Badge tone={STATUS_TONE[entry.current_status] ?? "default"}>
            {entry.current_status}
          </Badge>
        </div>
      ))}
    </div>
  );
}
