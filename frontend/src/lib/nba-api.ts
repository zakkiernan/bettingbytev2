import type {
  AbsenceImpactResponse,
  AdvancedTrendsResponse,
  ClutchResponse,
  DefensiveTrackingResponse,
  GameContextResponse,
  GameDetailResponse,
  GameHustleResponse,
  GameLogEntry,
  GameMatchupsResponse,
  GameShotChartResponse,
  TeamProfileResponse,
  HustleStatsResponse,
  LineMovementResponse,
  LiveGameResponse,
  LiveGameSummary,
  OnOffResponse,
  PlayTypesResponse,
  PlayerProfileResponse,
  PropBoardResponse,
  PropDetailResponse,
  RotationProfile,
  ShotChartResponse,
  ShotLocationsResponse,
  TrackingResponse,
  TrendPoint,
  WinProbResponse,
} from "@/types/api";

const NBA_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/nba`
  : "http://localhost:8000/api/nba";

async function nbaApiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${NBA_API_BASE}${path}`, {
    cache: "no-store",
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} - ${path}`);
  }
  return res.json() as Promise<T>;
}

export function fetchGamesToday(): Promise<GameDetailResponse[]> {
  return nbaApiFetch("/games/today");
}

export function fetchBoard(params?: {
  game_id?: string;
  recommended_only?: boolean;
  min_confidence?: number;
}): Promise<PropBoardResponse> {
  const qs = new URLSearchParams();
  if (params?.game_id) qs.set("game_id", params.game_id);
  if (params?.recommended_only) qs.set("recommended_only", "true");
  if (params?.min_confidence != null) {
    qs.set("min_confidence", String(params.min_confidence));
  }
  const query = qs.toString() ? `?${qs}` : "";
  return nbaApiFetch(`/props/board${query}`);
}

/**
 * Try today's board first. If empty, fall back to yesterday's highest-edge game.
 * Returns the board data + a label ("Tonight" or "Last Night").
 */
export async function fetchRecentBoard(): Promise<{
  board: PropBoardResponse;
  label: string;
}> {
  const emptyBoard: PropBoardResponse = {
    props: [],
    meta: { total_count: 0, game_count: 0, updated_at: undefined, stat_types_available: [] },
  };

  const todayBoard = await fetchBoard().catch(() => emptyBoard);
  if (todayBoard.props.length > 0) {
    return { board: todayBoard, label: "Tonight" };
  }

  // Fall back: get today's games list, find recent completed games with edges
  const games = await fetchGamesToday().catch(() => []);
  const gamesWithEdges = games
    .filter((g) => g.edge_count > 0)
    .sort((a, b) => b.edge_count - a.edge_count);

  if (gamesWithEdges.length > 0) {
    // Fetch board for the top game by edges
    const fallback = await fetchBoard({ game_id: gamesWithEdges[0].game_id }).catch(() => emptyBoard);
    if (fallback.props.length > 0) {
      return { board: fallback, label: "Tonight" };
    }
  }

  // Try yesterday's games by shifting game IDs (sequential in NBA)
  // If today's games have no edges either, fetch board for a few recent game IDs
  for (const g of games.slice(0, 3)) {
    const prevId = String(Number(g.game_id) - 10).padStart(10, "0");
    const prevBoard = await fetchBoard({ game_id: prevId }).catch(() => emptyBoard);
    if (prevBoard.props.length > 0) {
      return { board: prevBoard, label: "Last Night" };
    }
  }

  return { board: emptyBoard, label: "Tonight" };
}

export function fetchPropDetail(signalId: number): Promise<PropDetailResponse> {
  return nbaApiFetch(`/props/${signalId}`);
}

export function fetchLiveGames(): Promise<LiveGameSummary[]> {
  return nbaApiFetch("/live/active");
}

export function fetchLiveGame(gameId: string): Promise<LiveGameResponse> {
  return nbaApiFetch(`/live/${gameId}`);
}

export function fetchPlayerProfile(playerId: string): Promise<PlayerProfileResponse> {
  return nbaApiFetch(`/players/${playerId}`);
}

export function fetchPlayerGameLog(playerId: string, limit = 10): Promise<GameLogEntry[]> {
  return nbaApiFetch(`/players/${playerId}/game-log?limit=${limit}`);
}

export function fetchPlayerTrends(
  playerId: string,
  statType = "points",
  limit = 20,
): Promise<TrendPoint[]> {
  return nbaApiFetch(
    `/players/${playerId}/trends?stat_type=${encodeURIComponent(statType)}&limit=${limit}`,
  );
}

export function fetchAdvancedTrends(playerId: string, limit = 20): Promise<AdvancedTrendsResponse> {
  return nbaApiFetch(`/players/${playerId}/advanced-trends?limit=${limit}`);
}

export function fetchRotationProfile(playerId: string, limit = 20): Promise<RotationProfile> {
  return nbaApiFetch(`/players/${playerId}/rotation-profile?limit=${limit}`);
}

export function fetchAbsenceImpact(playerId: string): Promise<AbsenceImpactResponse> {
  return nbaApiFetch(`/players/${playerId}/absence-impact`);
}

export function fetchGameDetail(gameId: string): Promise<GameDetailResponse> {
  return nbaApiFetch(`/games/${gameId}`);
}

export function fetchGameContext(gameId: string): Promise<GameContextResponse> {
  return nbaApiFetch(`/games/${gameId}/context`);
}

export function fetchLineMovement(signalId: number): Promise<LineMovementResponse> {
  return nbaApiFetch(`/props/${signalId}/line-movement`);
}

// Player stats endpoints

export function fetchPlayerShotChart(
  playerId: string,
  opts?: { lastN?: number; gameId?: string },
): Promise<ShotChartResponse> {
  const qs = new URLSearchParams();
  if (opts?.lastN) qs.set("last_n", String(opts.lastN));
  if (opts?.gameId) qs.set("game_id", opts.gameId);
  const query = qs.toString() ? `?${qs}` : "";
  return nbaApiFetch(`/players/${playerId}/shot-chart${query}`);
}

export function fetchPlayerShotLocations(playerId: string): Promise<ShotLocationsResponse> {
  return nbaApiFetch(`/players/${playerId}/shot-locations`);
}

export function fetchPlayerPlayTypes(playerId: string): Promise<PlayTypesResponse> {
  return nbaApiFetch(`/players/${playerId}/play-types`);
}

export function fetchPlayerHustle(playerId: string): Promise<HustleStatsResponse> {
  return nbaApiFetch(`/players/${playerId}/hustle`);
}

export function fetchPlayerTracking(playerId: string): Promise<TrackingResponse> {
  return nbaApiFetch(`/players/${playerId}/tracking`);
}

export function fetchPlayerDefense(playerId: string): Promise<DefensiveTrackingResponse> {
  return nbaApiFetch(`/players/${playerId}/defense`);
}

export function fetchPlayerOnOff(playerId: string): Promise<OnOffResponse> {
  return nbaApiFetch(`/players/${playerId}/on-off`);
}

export function fetchPlayerClutch(playerId: string): Promise<ClutchResponse> {
  return nbaApiFetch(`/players/${playerId}/clutch`);
}

// Game stats endpoints

export function fetchGameMatchups(gameId: string): Promise<GameMatchupsResponse> {
  return nbaApiFetch(`/games/${gameId}/matchups`);
}

export function fetchGameWinProbability(gameId: string): Promise<WinProbResponse> {
  return nbaApiFetch(`/games/${gameId}/win-probability`);
}

export function fetchGameHustle(gameId: string): Promise<GameHustleResponse> {
  return nbaApiFetch(`/games/${gameId}/hustle`);
}

export function fetchGameShotChart(gameId: string): Promise<GameShotChartResponse> {
  return nbaApiFetch(`/games/${gameId}/shot-chart`);
}

// Team endpoints

export function fetchTeamProfile(teamId: string): Promise<TeamProfileResponse> {
  return nbaApiFetch(`/teams/${teamId}`);
}
