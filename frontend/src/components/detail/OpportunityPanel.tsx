import type { OpportunityContext } from "@/types/api";
import { ConfidenceBar } from "@/components/board/ConfidenceBar";

function StatRow({
  label,
  value,
  sub,
  emphasize,
}: {
  label: string;
  value: string;
  sub?: string;
  emphasize?: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl px-3 py-2 odd:bg-[color:var(--color-surface-elevated)]/40">
      <span className="text-sm text-[color:var(--color-text-secondary)]">{label}</span>
      <div className="text-right">
        <span className={`font-mono text-sm font-semibold ${emphasize ? "text-[color:var(--color-accent)]" : ""}`}>
          {value}
        </span>
        {sub && (
          <span className="ml-1 font-mono text-xs text-[color:var(--color-text-muted)]">
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

interface Props {
  opportunity: OpportunityContext;
}

export function OpportunityPanel({ opportunity: o }: Props) {
  const availColor =
    o.availability_modifier >= 0.9
      ? "text-[color:var(--color-positive)]"
      : o.availability_modifier >= 0.35
        ? "text-[color:var(--color-warning)]"
        : "text-[color:var(--color-negative)]";

  return (
    <div className="space-y-1">
      <StatRow
        label="Expected minutes"
        value={o.expected_minutes.toFixed(1)}
        sub={`season avg ${o.season_minutes_avg.toFixed(1)}`}
        emphasize
      />
      <StatRow
        label="Expected usage"
        value={`${(o.expected_usage_pct * 100).toFixed(1)}%`}
      />
      <StatRow
        label="Start rate"
        value={`${(o.expected_start_rate * 100).toFixed(0)}%`}
      />
      <StatRow
        label="Close rate"
        value={`${(o.expected_close_rate * 100).toFixed(0)}%`}
      />
      <StatRow
        label="Opportunity confidence"
        value={`${Math.round(o.opportunity_confidence * 100)}%`}
      />
      {o.vacated_minutes_bonus > 0.05 && (
        <StatRow
          label="Vacated mins bonus"
          value={`+${o.vacated_minutes_bonus.toFixed(2)}`}
          emphasize
        />
      )}
      {o.vacated_usage_bonus > 0.001 && (
        <StatRow
          label="Vacated usage bonus"
          value={`+${(o.vacated_usage_bonus * 100).toFixed(2)}%`}
          emphasize
        />
      )}

      <div className="pt-2 space-y-3">
        <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/35 px-3 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm text-[color:var(--color-text-secondary)]">
              Opportunity score
            </span>
            <span className="font-mono text-xs text-[color:var(--color-text-muted)]">
              {Math.round(Math.min(o.opportunity_score, 1) * 100)}%
            </span>
          </div>
          <ConfidenceBar value={Math.min(o.opportunity_score, 1)} />
        </div>

        <div className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/35 px-3 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm text-[color:var(--color-text-secondary)]">
              Role stability
            </span>
            <span className="font-mono text-xs text-[color:var(--color-text-muted)]">
              {Math.round(o.role_stability * 100)}%
            </span>
          </div>
          <ConfidenceBar value={o.role_stability} />
        </div>

        <div className="flex items-center justify-between rounded-xl px-3 py-2">
          <span className="text-sm text-[color:var(--color-text-secondary)]">
            Availability modifier
          </span>
          <span className={`font-mono text-sm font-semibold ${availColor}`}>
            {o.availability_modifier.toFixed(2)}×
          </span>
        </div>
      </div>
    </div>
  );
}
