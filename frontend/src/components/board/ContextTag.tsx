import { Badge } from "@/components/ui/badge";

const LABELS: Record<string, string> = {
  pregame_context: "lineup",
  official_injury_player: "injury:player",
  official_injury_team: "injury:team",
  none: "no context",
};

const TONES: Record<string, "success" | "live" | "default" | "danger"> = {
  pregame_context: "success",
  official_injury_player: "danger",
  official_injury_team: "live",
  none: "default",
};

interface Props {
  source?: string;
}

export function ContextTag({ source = "none" }: Props) {
  return (
    <Badge tone={TONES[source] ?? "default"}>
      {LABELS[source] ?? source}
    </Badge>
  );
}
