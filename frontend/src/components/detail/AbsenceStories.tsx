import type { AbsenceStoryEntry } from "@/types/api";
import { Card } from "@/components/ui/card";

interface Props {
  stories: AbsenceStoryEntry[];
}

export function AbsenceStories({ stories }: Props) {
  if (stories.length === 0) return null;

  return (
    <Card className="space-y-3">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">
        Absence impact
      </p>

      <div className="space-y-3">
        {stories.map((story, i) => {
          const statusColor =
            story.current_status === "Out"
              ? "text-[color:var(--color-negative)]"
              : story.current_status === "Doubtful"
                ? "text-[color:var(--caution)]"
                : "text-[color:var(--color-text-secondary)]";

          return (
            <div
              key={`${story.absent_player_id ?? story.absent_player_name}-${i}`}
              className="rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface-elevated)]/40 px-4 py-3"
            >
              <div className="flex items-center gap-2">
                <span className="font-semibold">{story.absent_player_name}</span>
                {story.current_status && (
                  <span className={`text-xs font-medium ${statusColor}`}>
                    {story.current_status}
                  </span>
                )}
              </div>

              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                {story.points_delta != null && story.points_delta !== 0 && (
                  <DeltaStat label="PPG" delta={story.points_delta} />
                )}
                {story.minutes_delta != null && story.minutes_delta !== 0 && (
                  <DeltaStat label="MPG" delta={story.minutes_delta} />
                )}
                {story.usage_delta != null && story.usage_delta !== 0 && (
                  <DeltaStat label="USG%" delta={story.usage_delta * 100} suffix="%" />
                )}
                {story.rebounds_delta != null && story.rebounds_delta !== 0 && (
                  <DeltaStat label="RPG" delta={story.rebounds_delta} />
                )}
                {story.assists_delta != null && story.assists_delta !== 0 && (
                  <DeltaStat label="APG" delta={story.assists_delta} />
                )}
              </div>

              <p className="mt-1.5 text-xs text-[color:var(--color-text-muted)]">
                {story.games_count} game{story.games_count !== 1 ? "s" : ""} sample
                {story.sample_confidence != null && (
                  <> · {Math.round(story.sample_confidence * 100)}% confidence</>
                )}
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function DeltaStat({
  label,
  delta,
  suffix = "",
}: {
  label: string;
  delta: number;
  suffix?: string;
}) {
  const color =
    delta > 0
      ? "text-[color:var(--color-positive)]"
      : "text-[color:var(--color-negative)]";
  return (
    <span className="text-[color:var(--color-text-secondary)]">
      {label}{" "}
      <span className={`font-mono font-semibold ${color}`}>
        {delta > 0 ? "+" : ""}
        {delta.toFixed(1)}
        {suffix}
      </span>
    </span>
  );
}
