interface Props {
  edge: number;
  probability: number;
  side: "over" | "under";
}

export function EdgeDisplay({ edge, probability, side }: Props) {
  const positive = side === "over" ? edge > 0 : edge > 0;
  const color = positive
    ? "text-[color:var(--color-positive)]"
    : "text-[color:var(--color-negative)]";
  const sign = edge >= 0 ? "+" : "";

  return (
    <div className="flex flex-col">
      <span className={`font-mono text-sm font-semibold ${color}`}>
        {sign}{edge.toFixed(1)}
      </span>
      <span className="font-mono text-xs text-[color:var(--color-text-muted)]">
        {Math.round(probability * 100)}%
      </span>
    </div>
  );
}
