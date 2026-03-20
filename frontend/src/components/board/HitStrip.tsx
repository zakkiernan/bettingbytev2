interface Props {
  values: number[];
  line: number;
  side: "OVER" | "UNDER";
}

export function HitStrip({ values, line, side }: Props) {
  return (
    <div className="flex items-center gap-0.5">
      {values.map((v, i) => {
        const hit = side === "OVER" ? v > line : v < line;
        return (
          <span
            key={i}
            className={`inline-block h-2 w-2 rounded-full ${
              hit
                ? "bg-[color:var(--color-positive)]"
                : "bg-[color:var(--color-negative)]"
            }`}
            title={`${v} ${hit ? "HIT" : "MISS"}`}
          />
        );
      })}
    </div>
  );
}
