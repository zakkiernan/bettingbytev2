import type {
  AbsenceImpactResponse,
  AdvancedTrendsResponse,
  GameContextResponse,
  GameDetailResponse,
  IngestionHealthResponse,
  LineMovementResponse,
  LiveGameResponse,
  LiveGameSummary,
  PlayerProfileResponse,
  PropBoardResponse,
  PropDetailResponse,
  RotationProfile,
  TrendPoint,
  GameLogEntry,
} from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      signal: controller.signal,
      ...opts,
    });
    if (!res.ok) {
      throw new Error(`API ${res.status} — ${path}`);
    }
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

export function fetchGamesToday(): Promise<GameDetailResponse[]> {
  return apiFetch("/games/today");
}

export function fetchBoard(params?: {
  game_id?: string;
  recommended_only?: boolean;
  min_confidence?: number;
}): Promise<PropBoardResponse> {
  const qs = new URLSearchParams();
  if (params?.game_id) qs.set("game_id", params.game_id);
  if (params?.recommended_only) qs.set("recommended_only", "true");
  if (params?.min_confidence != null)
    qs.set("min_confidence", String(params.min_confidence));
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch(`/props/board${query}`);
}

export function fetchPropDetail(signalId: number): Promise<PropDetailResponse> {
  return apiFetch(`/props/${signalId}`);
}

export function fetchHealth(): Promise<IngestionHealthResponse> {
  return apiFetch("/health");
}

export function fetchLiveGames(): Promise<LiveGameSummary[]> {
  return apiFetch("/live/active");
}

export function fetchLiveGame(gameId: string): Promise<LiveGameResponse> {
  return apiFetch(`/live/${gameId}`);
}

export function fetchPlayerProfile(
  playerId: string,
): Promise<PlayerProfileResponse> {
  return apiFetch(`/players/${playerId}`);
}

export function fetchPlayerGameLog(
  playerId: string,
  limit = 10,
): Promise<GameLogEntry[]> {
  return apiFetch(`/players/${playerId}/game-log?limit=${limit}`);
}

export function fetchPlayerTrends(
  playerId: string,
  statType = "points",
  limit = 20,
): Promise<TrendPoint[]> {
  return apiFetch(
    `/players/${playerId}/trends?stat_type=${encodeURIComponent(statType)}&limit=${limit}`,
  );
}

export function fetchAdvancedTrends(
  playerId: string,
  limit = 20,
): Promise<AdvancedTrendsResponse> {
  return apiFetch(`/players/${playerId}/advanced-trends?limit=${limit}`);
}

export function fetchRotationProfile(
  playerId: string,
  limit = 20,
): Promise<RotationProfile> {
  return apiFetch(`/players/${playerId}/rotation-profile?limit=${limit}`);
}

export function fetchAbsenceImpact(
  playerId: string,
): Promise<AbsenceImpactResponse> {
  return apiFetch(`/players/${playerId}/absence-impact`);
}

export function fetchGameDetail(gameId: string): Promise<GameDetailResponse> {
  return apiFetch(`/games/${gameId}`);
}

export function fetchGameContext(gameId: string): Promise<GameContextResponse> {
  return apiFetch(`/games/${gameId}/context`);
}

export function fetchLineMovement(
  signalId: number,
): Promise<LineMovementResponse> {
  return apiFetch(`/props/${signalId}/line-movement`);
}
