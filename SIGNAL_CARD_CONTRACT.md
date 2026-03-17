# Signal Card Contract

**Version:** 1.0  
**Date:** 2026-03-13  
**Status:** Draft

This document defines the canonical data contract for a BettingByte signal card — the atomic unit of output for the internal dashboard. Everything the dashboard displays must come from this contract. The API layer and any future frontend are expected to consume these shapes unchanged.

---

## Overview

A signal card represents a single player prop opportunity for a given game. It has two representations:

- **Card summary** — what appears in the slate/board view (one row per player prop)
- **Card detail** — the full breakdown accessible from a per-player drill-down

---

## 1. Signal Card Summary

Used for the main slate board. One card per player/prop/game.

```json
{
  "signal_id": 1042,
  "captured_at": "2026-03-13T22:00:00Z",
  "model_run_at": "2026-03-13T22:05:31Z",

  "game_id": "0022501001",
  "game_time_utc": "2026-03-14T00:10:00Z",
  "matchup": "BOS @ NYK",
  "home_team_abbreviation": "NYK",
  "away_team_abbreviation": "BOS",

  "player_id": "1629029",
  "player_name": "Jayson Tatum",
  "team_abbreviation": "BOS",

  "stat_type": "points",
  "line": 27.5,
  "over_odds": -115,
  "under_odds": -105,

  "projected_value": 29.8,
  "edge_over": 2.3,
  "edge_under": -2.3,
  "over_probability": 0.5912,
  "under_probability": 0.4088,

  "recommended_side": "OVER",
  "confidence": 0.71,

  "context_source": "pregame_context",
  "pregame_context_attached": true,
  "official_injury_attached": true,
  "official_injury_status": null,

  "key_factor": "Projected starter, teammate out (Brown - Out)"
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `signal_id` | int | DB primary key for this signal |
| `captured_at` | ISO datetime (UTC) | When the FanDuel line was captured |
| `model_run_at` | ISO datetime (UTC) | When the model generated this signal |
| `game_id` | string | NBA canonical game ID |
| `game_time_utc` | ISO datetime (UTC) | Scheduled tip-off time |
| `matchup` | string | Human-readable `"AWAY @ HOME"` |
| `home_team_abbreviation` | string | Home team 3-letter code |
| `away_team_abbreviation` | string | Away team 3-letter code |
| `player_id` | string | NBA canonical player ID |
| `player_name` | string | Full display name |
| `team_abbreviation` | string | Player's team 3-letter code |
| `stat_type` | string | Prop category — currently always `"points"` |
| `line` | float | Sportsbook over/under line |
| `over_odds` | int | American odds for OVER |
| `under_odds` | int | American odds for UNDER |
| `projected_value` | float | Model's projected stat value |
| `edge_over` | float | `projected_value - line` |
| `edge_under` | float | `line - projected_value` |
| `over_probability` | float | Model P(actual > line), range [0, 1] |
| `under_probability` | float | Model P(actual < line), range [0, 1] |
| `recommended_side` | `"OVER"` \| `"UNDER"` \| `null` | Recommendation if thresholds are met; null if no edge or confidence too low |
| `confidence` | float | Composite model confidence, range [0, 1] |
| `context_source` | string | See Context Source Values below |
| `pregame_context_attached` | bool | Whether pregame context (lineup/availability) was used |
| `official_injury_attached` | bool | Whether an official NBA injury report was attached |
| `official_injury_status` | string \| null | Player's own status if on official report: `"Out"`, `"Doubtful"`, `"Questionable"`, `"Probable"`, or `null` |
| `key_factor` | string \| null | Human-readable summary of the most influential context signal |

### Context Source Values

| Value | Meaning |
|---|---|
| `"pregame_context"` | Projected lineup/availability data attached and used |
| `"official_injury_player"` | Player found by name in official NBA injury report |
| `"official_injury_team"` | Team-level official injury data used (no player-specific match) |
| `"none"` | No external context — model ran on historical features only |

### Recommendation Thresholds (current)

A `recommended_side` is set only when all three hold:
- `|edge| >= 1.0`
- `probability >= 0.54`
- `confidence >= 0.58`

---

## 2. Signal Card Detail

The full per-player breakdown. Extends the summary with opportunity context, points breakdown, and recent game log.

```json
{
  // All fields from Signal Card Summary, plus:

  "opportunity": {
    "expected_minutes": 36.2,
    "expected_rotation_minutes": 35.8,
    "expected_usage_pct": 0.301,
    "expected_start_rate": 0.94,
    "expected_close_rate": 0.81,
    "availability_modifier": 1.0,
    "vacated_minutes_bonus": 1.8,
    "vacated_usage_bonus": 0.012,
    "role_stability": 0.74,
    "rotation_role_score": 0.88,
    "offensive_role_score": 0.91,
    "opportunity_score": 0.83,
    "opportunity_confidence": 0.71
  },

  "points_breakdown": {
    "base_scoring": 24.1,
    "recent_form_adjustment": 1.4,
    "minutes_adjustment": 0.8,
    "usage_adjustment": 1.2,
    "efficiency_adjustment": 0.6,
    "opponent_adjustment": 0.9,
    "pace_adjustment": 0.8,
    "context_adjustment": 0.0,
    "points_per_minute": 0.794,
    "projected_points": 29.8
  },

  "injury_context": [
    {
      "player_name": "Jaylen Brown",
      "team_abbreviation": "BOS",
      "current_status": "Out",
      "reason": "Knee"
    }
  ],

  "distribution": {
    "projected_value": 29.8,
    "std": 6.1,
    "line": 27.5
  },

  "features_snapshot": {
    "days_rest": 2,
    "back_to_back": false,
    "sample_size": 52,
    "season_points_avg": 27.4,
    "last10_points_avg": 29.1,
    "last5_points_avg": 30.2,
    "season_minutes_avg": 35.6,
    "last10_minutes_avg": 36.4,
    "season_usage_pct": 0.296,
    "opponent_def_rating": 112.4,
    "opponent_pace": 99.2,
    "team_pace": 101.1
  },

  "recent_game_log": [
    {
      "game_id": "0022500988",
      "game_date": "2026-03-11T00:00:00Z",
      "opponent": "MIL",
      "is_home": true,
      "minutes": 37.0,
      "points": 31.0,
      "rebounds": 8.0,
      "assists": 4.0
    }
    // ... up to 10 entries
  ]
}
```

### Opportunity Sub-Object

| Field | Type | Description |
|---|---|---|
| `expected_minutes` | float | Final projected minutes after all adjustments |
| `expected_rotation_minutes` | float | Rotation-data-derived minutes estimate |
| `expected_usage_pct` | float | Final projected box-score usage |
| `expected_start_rate` | float | Probability of starting, range [0, 1] |
| `expected_close_rate` | float | Probability of closing 4th quarter, range [0, 1] |
| `availability_modifier` | float | Multiplier from availability gate (1.0 = fully available, < 0.15 = unavailable) |
| `vacated_minutes_bonus` | float | Minutes bonus from teammate absences |
| `vacated_usage_bonus` | float | Usage bonus from teammate absences |
| `role_stability` | float | Stability of role signal, range [0, 1] |
| `rotation_role_score` | float | Rotation-derived role quality, range [0, 1.25] |
| `offensive_role_score` | float | Offensive opportunity quality, range [0, 1.25] |
| `opportunity_score` | float | Final composite opportunity, range [0, 1.25] |
| `opportunity_confidence` | float | Confidence in opportunity estimate, range [0, 1] |

### Points Breakdown Sub-Object

| Field | Type | Description |
|---|---|---|
| `base_scoring` | float | `expected_minutes × points_per_minute` |
| `recent_form_adjustment` | float | Delta from L5/L10 vs season scoring trend |
| `minutes_adjustment` | float | Delta from projected vs season minutes |
| `usage_adjustment` | float | Delta from projected vs season usage |
| `efficiency_adjustment` | float | Delta from L10 TS%/FG% vs season |
| `opponent_adjustment` | float | Delta from opponent defensive rating |
| `pace_adjustment` | float | Delta from game pace vs league average |
| `context_adjustment` | float | Home/B2B/rest adjustments |
| `points_per_minute` | float | Blended PPM used in projection |
| `projected_points` | float | Final sum, floored at 0 |

### Distribution Sub-Object

| Field | Type | Description |
|---|---|---|
| `projected_value` | float | Model projection (same as top-level) |
| `std` | float | Assumed distribution sigma for probability calc |
| `line` | float | Sportsbook line the probabilities are computed against |

---

## 3. Ingestion Health Card

Displayed on the dashboard header or a dedicated health panel. Covers the key pipeline signals.

```json
{
  "health_captured_at": "2026-03-13T22:05:31Z",

  "lines": {
    "tonight_game_count": 6,
    "tonight_prop_count": 84,
    "stale_captures": 2,
    "oldest_capture_age_minutes": 47,
    "sportsbook": "fanduel"
  },

  "rotations": {
    "coverage_pct": 99.27,
    "pending": 0,
    "retry": 0,
    "quarantined": 7
  },

  "injury_reports": {
    "latest_report_date": "2026-03-13",
    "reports_stored": 600,
    "entries_stored": 78181
  },

  "pregame_context": {
    "tonight_games_with_context": 5,
    "tonight_games_missing_context": 1
  },

  "signal_run": {
    "last_run_at": "2026-03-13T22:05:31Z",
    "signals_generated": 84,
    "signals_with_recommendation": 12,
    "signals_missing_source_game": 0
  }
}
```

### Stale Captures

A prop capture is considered **stale** if its `captured_at` is more than 60 minutes before `model_run_at`. Stale captures should be flagged visually on the dashboard — the line may have moved since capture.

---

## 4. API Endpoints (Internal Dashboard)

These map to the internal dashboard screens. All responses are JSON.

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /api/v1/board` | `PropBoardResponse` (list of card summaries + meta) | Tonight's slate; filterable by `game_id`, `recommended_side`, `min_confidence` |
| `GET /api/v1/props/{signal_id}` | Signal card detail | Full breakdown + game log |
| `GET /api/v1/health` | Ingestion health card | Pipeline status snapshot |
| `GET /api/v1/games` | List of tonight's games with counts | Sidebar nav data |

---

## 5. Null / Missing Value Semantics

- `recommended_side: null` — no edge met thresholds; **not** a "don't bet" recommendation, just insufficient signal
- `official_injury_status: null` — player not found on official report (most players won't be)
- `key_factor: null` — no context was strong enough to surface as the dominant signal
- `confidence: 0.0` — data was too sparse to produce a reliable estimate; treat signal as informational only
- `projected_value: 0.0` with `edge_over: 0.0` — model failed to produce a projection; should not appear on dashboard

---

## 6. Versioning

The `model_name` and `model_version` fields stored in the DB signals table (`pregame_points_baseline`, `v3`) are not surfaced directly on the card — they're internal audit fields. If the model version changes, old signals should not be mixed with new ones in the same board view.

---

_This contract drives the internal dashboard build. Any changes to model output fields must be reflected here before the dashboard is updated._
