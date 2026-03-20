import { fetchAbsenceImpact } from "@/lib/api";
import { AbsenceImpactMatrix } from "@/components/detail/AbsenceImpactMatrix";

export async function AbsenceSection({ playerId }: { playerId: string }) {
  const absenceImpact = await fetchAbsenceImpact(playerId).catch(() => null);

  if (
    !absenceImpact ||
    (absenceImpact.when_player_sits.length === 0 && absenceImpact.when_others_sit.length === 0)
  ) {
    return null;
  }

  return <AbsenceImpactMatrix impact={absenceImpact} />;
}
