// TypeScript types mirroring the backend signal card contract.
// Keep in sync with api/schemas/ and SIGNAL_CARD_CONTRACT.md.

export interface TeamBrief {
  team_id: string;
  abbreviation: string;
  full_name: string;
  city?: string;
  nickname?: string;
}

export interface GameDetailResponse {
  game_id: string;
  season?: string;
  game_date?: string;
  game_time_utc?: string;
  home_team: TeamBrief;
  away_team: TeamBrief;
  game_status?: number;
  status_text?: string;
  prop_count: number;
  edge_count: number;
}

export interface PropBoardRow {
  signal_id: number;
  game_id: string;
  game_time_utc?: string;
  home_team_abbreviation: string;
  away_team_abbreviation: string;
  player_id: string;
  player_name: string;
  team_abbreviation: string;
  stat_type: string;
  line: number;
  over_odds: number;
  under_odds: number;
  projected_value: number;
  edge_over: number;
  edge_under: number;
  over_probability: number;
  under_probability: number;
  confidence: number;
  recommended_side: "OVER" | "UNDER" | null;
  recent_hit_rate?: number;
  recent_games_count?: number;
  key_factor?: string;
  recent_values?: number[] | null;
  opening_line?: number | null;
}

export interface PropBoardMeta {
  total_count: number;
  game_count: number;
  updated_at?: string;
  stat_types_available: string[];
}

export interface PropBoardResponse {
  props: PropBoardRow[];
  meta: PropBoardMeta;
}

export interface PointsBreakdown {
  base_scoring: number;
  recent_form_adjustment: number;
  minutes_adjustment: number;
  usage_adjustment: number;
  efficiency_adjustment: number;
  opponent_adjustment: number;
  pace_adjustment: number;
  context_adjustment: number;
  expected_minutes: number;
  expected_usage_pct: number;
  points_per_minute: number;
  projected_points: number;
}

export interface InjuryEntry {
  player_name: string;
  team_abbreviation: string;
  current_status: "Out" | "Doubtful" | "Questionable" | "Probable";
  reason: string;
}

export interface OpportunityContext {
  expected_minutes: number;
  season_minutes_avg: number;
  expected_usage_pct: number;
  expected_start_rate: number;
  expected_close_rate: number;
  role_stability: number;
  opportunity_score: number;
  opportunity_confidence: number;
  availability_modifier: number;
  vacated_minutes_bonus: number;
  vacated_usage_bonus: number;
  injury_entries: InjuryEntry[];
}

export interface FeatureSnapshot {
  team_abbreviation: string;
  opponent_abbreviation: string;
  is_home: boolean;
  days_rest?: number;
  back_to_back: boolean;
  sample_size: number;
  season_points_avg?: number;
  last10_points_avg?: number;
  last5_points_avg?: number;
  season_minutes_avg?: number;
  last10_minutes_avg?: number;
  last5_minutes_avg?: number;
  season_usage_pct?: number;
  opponent_def_rating?: number;
  opponent_pace?: number;
  team_pace?: number;
  context_source?: string;
}

export interface GameLogEntry {
  game_id: string;
  game_date?: string;
  opponent: string;
  is_home: boolean;
  minutes: number;
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  blocks: number;
  turnovers: number;
  threes_made: number;
  field_goals_made: number;
  field_goals_attempted: number;
  free_throws_made: number;
  free_throws_attempted: number;
  plus_minus: number;
}

export interface LineupContextNarrative {
  expected_start?: boolean | null;
  starter_confidence?: number | null;
  late_scratch_risk?: number | null;
  missing_teammates_top7?: number | null;
  missing_high_usage_teammates?: number | null;
  missing_primary_ballhandler?: boolean | null;
  missing_frontcourt_rotation_piece?: boolean | null;
  vacated_minutes_proxy?: number | null;
  vacated_usage_proxy?: number | null;
  pregame_context_confidence?: number | null;
  projected_lineup_confirmed?: boolean | null;
  rotation_depletion?: string | null;
}

export interface AbsenceStoryEntry {
  absent_player_name: string;
  absent_player_id?: string | null;
  current_status?: string | null;
  points_delta?: number | null;
  minutes_delta?: number | null;
  usage_delta?: number | null;
  rebounds_delta?: number | null;
  assists_delta?: number | null;
  games_count: number;
  sample_confidence?: number | null;
}

export interface NarrativeContext {
  lineup_context?: LineupContextNarrative | null;
  absence_stories: AbsenceStoryEntry[];
  matchup_note?: string | null;
}

export interface PropDetailResponse extends PropBoardRow {
  breakdown: PointsBreakdown;
  opportunity: OpportunityContext;
  features: FeatureSnapshot;
  recent_game_log: GameLogEntry[];
  narrative?: NarrativeContext | null;
}

export interface SeasonAverages {
  games_played: number;
  ppg: number;
  rpg: number;
  apg: number;
  mpg: number;
  fg_pct: number;
  three_pct: number;
  ft_pct: number;
  usage_pct: number;
  ts_pct: number;
}

export interface TrendPoint {
  game_date?: string;
  value: number;
  line?: number | null;
  hit?: boolean | null;
}

export interface PlayerProfileResponse {
  player_id: string;
  full_name: string;
  first_name?: string | null;
  last_name?: string | null;
  team_abbreviation: string;
  team_full_name: string;
  season_averages: SeasonAverages;
  active_props: PropBoardRow[];
}

export interface LivePlayerRow {
  player_id: string;
  player_name: string;
  team_abbreviation: string;
  stat_type: string;
  line: number;
  current_stat: number;
  live_projection: number;
  pace_projection: number;
  live_edge: number;
  pregame_projection: number;
  on_court: boolean;
  minutes_played: number;
  fouls: number;
}

export interface LiveAlert {
  id: string;
  type:
    | "edge_emerged"
    | "cold_start"
    | "hot_start"
    | "pace_shift"
    | "foul_trouble";
  player_name: string;
  message: string;
  edge_value?: number | null;
  created_at: string;
}

export interface PaceSummary {
  current_pace: number;
  expected_pace: number;
  scoring_impact_pct: number;
}

export interface LiveGameSummary {
  game_id: string;
  home_team: TeamBrief;
  away_team: TeamBrief;
  home_score: number;
  away_score: number;
  period: number;
  game_clock: string;
  live_edge_count: number;
  updated_at?: string | null;
}

export interface LiveGameResponse extends LiveGameSummary {
  players: LivePlayerRow[];
  alerts: LiveAlert[];
  pace: PaceSummary;
}

// Advanced trends types

export interface AdvancedTrendPoint {
  game_id: string;
  game_date?: string;
  opponent?: string;
  is_home?: boolean;
  minutes?: number;
  usage_percentage?: number;
  true_shooting_percentage?: number;
  effective_field_goal_percentage?: number;
  pace?: number;
  offensive_rating?: number;
  defensive_rating?: number;
  net_rating?: number;
  touches?: number;
  passes?: number;
  pie?: number;
}

export interface AdvancedTrendsResponse {
  player_id: string;
  player_name: string;
  game_count: number;
  points: AdvancedTrendPoint[];
}

// Rotation types

export interface RotationGameEntry {
  game_id: string;
  game_date?: string;
  opponent?: string;
  started?: boolean;
  closed_game?: boolean;
  stint_count?: number;
  total_shift_duration_real?: number;
  avg_shift_duration_real?: number;
}

export interface RotationProfile {
  player_id: string;
  player_name: string;
  games_tracked: number;
  start_rate: number;
  close_rate: number;
  avg_stint_count: number;
  avg_minutes: number;
  recent_games: RotationGameEntry[];
}

// Absence impact types

export interface AbsenceImpactEntry {
  source_player_id: string;
  source_player_name: string;
  beneficiary_player_id: string;
  beneficiary_player_name: string;
  team_abbreviation: string;
  points_delta?: number;
  rebounds_delta?: number;
  assists_delta?: number;
  minutes_delta?: number;
  usage_delta?: number;
  touches_delta?: number;
  source_out_game_count: number;
  beneficiary_active_game_count: number;
  impact_score?: number;
  sample_confidence?: number;
}

export interface AbsenceImpactResponse {
  player_id: string;
  player_name: string;
  when_player_sits: AbsenceImpactEntry[];
  when_others_sit: AbsenceImpactEntry[];
}

// Game context types

export interface LineupEntry {
  player_id?: string;
  player_name?: string;
  expected_start?: boolean;
  starter_confidence?: number;
  late_scratch_risk?: number;
  official_available?: boolean;
  projected_available?: boolean;
}

export interface TeamDefenseSnapshot {
  defensive_rating?: number;
  pace?: number;
  opponent_points_per_game?: number;
  opponent_field_goal_percentage?: number;
  opponent_three_point_percentage?: number;
}

export interface TeamGameContext {
  team_abbreviation: string;
  team_name?: string;
  expected_lineup: LineupEntry[];
  injury_entries: InjuryEntry[];
  defense?: TeamDefenseSnapshot;
  teammate_out_count_top7?: number;
  teammate_out_count_top9?: number;
}

export interface GameContextResponse {
  game_id: string;
  game_date?: string;
  game_time_utc?: string;
  home_team: TeamGameContext;
  away_team: TeamGameContext;
  pace_matchup?: number;
}

// Line movement types

export interface LineMovementPoint {
  captured_at: string;
  line: number;
  over_odds: number;
  under_odds: number;
  market_phase: string;
}

export interface LineMovementResponse {
  signal_id: number;
  game_id: string;
  player_id: string;
  player_name: string;
  stat_type: string;
  current_line: number;
  opening_line?: number;
  line_movement?: number;
  snapshots: LineMovementPoint[];
}

// Health types

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
