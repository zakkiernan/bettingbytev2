export interface TeamBrief {
  team_id: string;
  abbreviation: string;
  full_name: string;
  city?: string;
  nickname?: string;
}

export interface LinesHealth {
  tonight_game_count: number;
  tonight_prop_count: number;
  stale_captures: number;
  oldest_capture_age_minutes?: number;
  sportsbook: string;
}

export interface RotationsHealth {
  coverage_pct: number;
  pending: number;
  retry: number;
  quarantined: number;
}

export interface InjuryReportsHealth {
  latest_report_date?: string;
  reports_stored: number;
  entries_stored: number;
}

export interface PregameContextHealth {
  tonight_games_with_context: number;
  tonight_games_missing_context: number;
}

export interface SignalRunHealth {
  last_run_at?: string;
  signals_generated: number;
  signals_with_recommendation: number;
  signals_missing_source_game: number;
}

export interface IngestionHealthResponse {
  health_captured_at: string;
  lines: LinesHealth;
  rotations: RotationsHealth;
  injury_reports: InjuryReportsHealth;
  pregame_context: PregameContextHealth;
  signal_run: SignalRunHealth;
}
