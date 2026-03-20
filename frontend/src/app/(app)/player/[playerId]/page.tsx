import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ playerId: string }>;
}

export default async function LegacyPlayerPage({ params }: PageProps) {
  const { playerId } = await params;
  redirect(`/nba/player/${playerId}`);
}
