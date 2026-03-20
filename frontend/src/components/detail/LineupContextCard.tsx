import type { LineupContextNarrative } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  context: LineupContextNarrative;
}

function ContextRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm text-[color:var(--color-text-secondary)]">{label}</span>
      <span className="font-mono text-sm font-semibold">{children}</span>
    </div>
  );
}

export function LineupContextCard({ context }: Props) {
  const depletionColors: Record<string, string> = {
    none: "text-[color:var(--color-text-muted)]",
    low: "text-[color:var(--color-text-secondary)]",
    moderate: "text-[color:var(--caution)]",
    high: "text-[color:var(--color-negative)]",
    severe: "text-[color:var(--color-negative)]",
  };

  return (
    <Card className="space-y-3">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Lineup context
      </p>

      <div className="divide-y divide-[color:var(--color-border)]">
        {context.expected_start != null && (
          <ContextRow label="Expected starter">
            <span className={context.expected_start ? "text-[color:var(--color-positive)]" : "text-[color:var(--color-text-secondary)]"}>
              {context.expected_start ? "Yes" : "No"}
            </span>
            {context.starter_confidence != null && (
              <span className="ml-2 text-xs text-[color:var(--color-text-muted)]">
                ({Math.round(context.starter_confidence * 100)}%)
              </span>
            )}
          </ContextRow>
        )}

        {context.late_scratch_risk != null && context.late_scratch_risk > 0.1 && (
          <ContextRow label="Late scratch risk">
            <span className="text-[color:var(--caution)]">
              {Math.round(context.late_scratch_risk * 100)}%
            </span>
          </ContextRow>
        )}

        {context.missing_teammates_top7 != null && context.missing_teammates_top7 > 0 && (
          <ContextRow label="Missing top-7 teammates">
            <span className="text-[color:var(--color-negative)]">
              {context.missing_teammates_top7}
            </span>
          </ContextRow>
        )}

        {context.vacated_minutes_proxy != null && context.vacated_minutes_proxy > 0 && (
          <ContextRow label="Vacated minutes">
            <span className="text-[color:var(--color-positive)]">
              +{context.vacated_minutes_proxy.toFixed(1)}
            </span>
          </ContextRow>
        )}

        {context.vacated_usage_proxy != null && context.vacated_usage_proxy > 0 && (
          <ContextRow label="Vacated usage">
            <span className="text-[color:var(--color-positive)]">
              +{(context.vacated_usage_proxy * 100).toFixed(1)}%
            </span>
          </ContextRow>
        )}

        {context.rotation_depletion != null && context.rotation_depletion !== "none" && (
          <ContextRow label="Rotation depletion">
            <span className={depletionColors[context.rotation_depletion] ?? ""}>
              {context.rotation_depletion}
            </span>
          </ContextRow>
        )}

        {context.pregame_context_confidence != null && (
          <ContextRow label="Context confidence">
            {Math.round(context.pregame_context_confidence * 100)}%
          </ContextRow>
        )}
      </div>
    </Card>
  );
}
