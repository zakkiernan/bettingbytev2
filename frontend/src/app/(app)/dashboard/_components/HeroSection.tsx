import Link from "next/link";
import { fetchGamesToday, fetchLiveGames } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export default async function HeroSection() {
  const [games, liveGames] = await Promise.all([
    fetchGamesToday().catch(() => []),
    fetchLiveGames().catch(() => []),
  ]);

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">Tonight&apos;s Edge</h1>
        {liveGames.length > 0 && (
          <Link href="/nba/live">
            <Badge tone="live" className="gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--color-accent)] opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[color:var(--color-accent)]" />
              </span>
              {liveGames.length} {liveGames.length === 1 ? "game" : "games"} live
            </Badge>
          </Link>
        )}
      </div>
      <p className="text-sm text-[color:var(--color-text-secondary)]">
        {dateStr}
        {games.length > 0 && (
          <>
            {" "}&middot;{" "}
            <span className="font-mono font-semibold text-[color:var(--color-text-primary)]">
              {games.length}
            </span>{" "}
            NBA {games.length === 1 ? "game" : "games"}
          </>
        )}
      </p>
    </div>
  );
}
