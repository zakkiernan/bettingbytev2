import { TrendingDown, TrendingUp, Minus } from "lucide-react";

interface Props {
  openingLine: number;
  currentLine: number;
}

export function LineMovement({ openingLine, currentLine }: Props) {
  const diff = currentLine - openingLine;
  if (diff === 0) {
    return (
      <div className="flex items-center gap-1 text-xs text-[color:var(--color-text-muted)]">
        <Minus className="h-3 w-3" />
        <span className="font-mono">{currentLine}</span>
      </div>
    );
  }

  const moved = diff > 0 ? "up" : "down";
  const Icon = moved === "up" ? TrendingUp : TrendingDown;
  const color =
    moved === "up"
      ? "text-[color:var(--color-positive)]"
      : "text-[color:var(--color-negative)]";

  return (
    <div className={`flex items-center gap-1 text-xs ${color}`}>
      <Icon className="h-3 w-3" />
      <span className="font-mono">
        {openingLine} → {currentLine}
      </span>
    </div>
  );
}
