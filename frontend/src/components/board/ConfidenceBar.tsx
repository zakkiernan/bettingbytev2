interface Props {
  value: number; // 0–1
}

export function ConfidenceBar({ value }: Props) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70
      ? "bg-[color:var(--color-positive)]"
      : pct >= 50
        ? "bg-[color:var(--color-accent)]"
        : "bg-[color:var(--color-text-muted)]";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[color:var(--color-surface-elevated)]">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 font-mono text-xs text-[color:var(--color-text-secondary)]">
        {pct}%
      </span>
    </div>
  );
}
