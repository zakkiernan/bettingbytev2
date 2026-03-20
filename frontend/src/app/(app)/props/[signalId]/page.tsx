import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ signalId: string }>;
}

export default async function LegacyPropDetailPage({ params }: PageProps) {
  const { signalId } = await params;
  redirect(`/nba/props/${signalId}`);
}
