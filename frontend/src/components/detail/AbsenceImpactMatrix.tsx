import type { AbsenceImpactResponse, AbsenceImpactEntry } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  impact: AbsenceImpactResponse;
}

function DeltaValue({ value, suffix = "" }: { value?: number | null; suffix?: string }) {
  if (value == null || value === 0) return <span className="text-[color:var(--color-text-muted)]">—</span>;
  const color = value > 0 ? "text-[color:var(--color-positive)]" : "text-[color:var(--color-negative)]";
  return (
    <span className={`font-mono font-semibold ${color}`}>
      {value > 0 ? "+" : ""}{value.toFixed(1)}{suffix}
    </span>
  );
}

function ImpactTable({
  title,
  entries,
  nameKey,
}: {
  title: string;
  entries: AbsenceImpactEntry[];
  nameKey: "source_player_name" | "beneficiary_player_name";
}) {
  if (entries.length === 0) {
    return (
      <div>
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
          {title}
        </p>
        <p className="text-sm text-[color:var(--color-text-muted)]">No data available.</p>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        {title}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[color:var(--color-border)] text-left text-xs uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
              <th className="pb-2 pr-4">Player</th>
              <th className="pb-2 pr-3 text-right">PPG</th>
              <th className="pb-2 pr-3 text-right">MPG</th>
              <th className="pb-2 pr-3 text-right">USG%</th>
              <th className="pb-2 pr-3 text-right">Games</th>
              <th className="pb-2 text-right">Conf</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]">
            {entries.map((entry, i) => (
              <tr key={`${entry.source_player_id}-${entry.beneficiary_player_id}-${i}`}>
                <td className="py-2 pr-4 font-semibold">{entry[nameKey]}</td>
                <td className="py-2 pr-3 text-right"><DeltaValue value={entry.points_delta} /></td>
                <td className="py-2 pr-3 text-right"><DeltaValue value={entry.minutes_delta} /></td>
                <td className="py-2 pr-3 text-right">
                  <DeltaValue value={entry.usage_delta != null ? entry.usage_delta * 100 : null} suffix="%" />
                </td>
                <td className="py-2 pr-3 text-right font-mono text-[color:var(--color-text-secondary)]">
                  {entry.source_out_game_count}
                </td>
                <td className="py-2 text-right font-mono text-[color:var(--color-text-secondary)]">
                  {entry.sample_confidence != null ? `${Math.round(entry.sample_confidence * 100)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AbsenceImpactMatrix({ impact }: Props) {
  return (
    <Card className="space-y-6">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Absence impact
      </p>

      <ImpactTable
        title="When others sit (this player benefits)"
        entries={impact.when_others_sit}
        nameKey="source_player_name"
      />

      <ImpactTable
        title="When this player sits (others benefit)"
        entries={impact.when_player_sits}
        nameKey="beneficiary_player_name"
      />
    </Card>
  );
}
