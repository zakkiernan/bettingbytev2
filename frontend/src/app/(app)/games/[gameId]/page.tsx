import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ gameId: string }>;
}

export default async function LegacyGameDetailPage({ params }: PageProps) {
  const { gameId } = await params;
  redirect(`/nba/games/${gameId}`);
}
