# NBA API Endpoints - Complete Reference
## nba_api Python Library (github.com/swar/nba_api)

Total endpoints: **135**
Base URL: `https://stats.nba.com/stats/`

---

## TABLE OF CONTENTS

1. [Shot Chart Endpoints](#1-shot-chart-endpoints)
2. [Shot Location / Zone Endpoints](#2-shot-location--zone-endpoints)
3. [Player Tracking - Shooting](#3-player-tracking---shooting)
4. [Clutch Stats](#4-clutch-stats)
5. [Hustle Stats](#5-hustle-stats)
6. [Matchup Data](#6-matchup-data)
7. [Lineup Stats](#7-lineup-stats)
8. [On/Off Court Stats](#8-onoff-court-stats)
9. [Player Dashboard Endpoints](#9-player-dashboard-endpoints)
10. [Team Dashboard Endpoints](#10-team-dashboard-endpoints)
11. [Shooting Splits](#11-shooting-splits)
12. [Synergy / Play Type Data](#12-synergy--play-type-data)
13. [Defensive Tracking](#13-defensive-tracking)
14. [Player Tracking - Passes](#14-player-tracking---passes)
15. [Player Tracking - Rebounds](#15-player-tracking---rebounds)
16. [Player Tracking - Speed/Distance](#16-player-tracking---speeddistance)
17. [Draft Combine Stats](#17-draft-combine-stats)
18. [Win Probability / Game Flow](#18-win-probability--game-flow)
19. [Box Score Endpoints](#19-box-score-endpoints)
20. [Play-by-Play](#20-play-by-play)
21. [Game Rotation](#21-game-rotation)
22. [Estimated Metrics](#22-estimated-metrics)
23. [League-Wide Stats](#23-league-wide-stats)
24. [Player Career / Profile](#24-player-career--profile)
25. [Player / Team Comparison](#25-player--team-comparison)
26. [Game Finders / Logs](#26-game-finders--logs)
27. [Leaders & Rankings](#27-leaders--rankings)
28. [Scoreboard & Schedule](#28-scoreboard--schedule)
29. [Reference / Metadata Endpoints](#29-reference--metadata-endpoints)
30. [Video Endpoints](#30-video-endpoints)
31. [Miscellaneous](#31-miscellaneous)

---

## 1. SHOT CHART ENDPOINTS

### ShotChartDetail
- **Class:** `ShotChartDetail`
- **URL:** `/shotchartdetail`
- **Data:** Every individual shot attempt with XY coordinates
- **Datasets:**
  - `Shot_Chart_Detail` - GAME_ID, PLAYER_ID, PLAYER_NAME, TEAM_ID, PERIOD, MINUTES_REMAINING, SECONDS_REMAINING, EVENT_TYPE, ACTION_TYPE, SHOT_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, SHOT_DISTANCE, **LOC_X, LOC_Y**, SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG, GAME_DATE, HTM, VTM
  - `LeagueAverages` - SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, FGA, FGM, FG_PCT
- **Use cases:** Hot/cold zone mapping, shot selection analysis, shot quality scoring

### ShotChartLeagueWide
- **Class:** `ShotChartLeagueWide`
- **URL:** `/shotchartleaguewide`
- **Data:** League-wide shooting by zone (aggregated, no XY)
- **Dataset:** `League_Wide` - GRID_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, FGA, FGM, FG_PCT

### ShotChartLineupDetail
- **Class:** `ShotChartLineupDetail`
- **URL:** `/shotchartlineupdetail`
- **Data:** Shot chart data for specific lineup combinations (with XY coordinates)
- **Datasets:**
  - `ShotChartLineupDetail` - GROUP_ID, GROUP_NAME + same shot detail columns as ShotChartDetail
  - `ShotChartLineupLeagueAverage` - Zone-level league averages

---

## 2. SHOT LOCATION / ZONE ENDPOINTS

### LeagueDashPlayerShotLocations
- **Class:** `LeagueDashPlayerShotLocations`
- **URL:** `/leaguedashplayershotlocations`
- **Data:** FGM/FGA/FG_PCT for every player across 7 court zones
- **Zones:** Restricted Area, In The Paint (Non-RA), Mid-Range, Left Corner 3, Right Corner 3, Above the Break 3, Backcourt
- **Use cases:** Zone-based shooting profiles, hot zone identification

### LeagueDashTeamShotLocations
- **Class:** `LeagueDashTeamShotLocations`
- **URL:** `/leaguedashteamshotlocations`
- **Data:** Same 7-zone breakdown at team level
- **Use cases:** Team shot distribution analysis, opponent zone tendencies

---

## 3. PLAYER TRACKING - SHOOTING

### PlayerDashPtShots
- **Class:** `PlayerDashPtShots`
- **URL:** `/playerdashptshots`
- **Data:** Player shooting broken down by tracking dimensions
- **Datasets:**
  - `ClosestDefenderShooting` - by defender proximity
  - `ClosestDefender10ftPlusShooting` - wide open shots
  - `DribbleShooting` - by dribble count before shot
  - `GeneralShooting` - by shot type
  - `ShotClockShooting` - by shot clock remaining
  - `TouchTimeShooting` - by seconds holding ball
  - `Overall` - aggregate
- **Columns:** FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, FG2M/A/PCT, FG3M/A/PCT

### TeamDashPtShots
- **Class:** `TeamDashPtShots`
- **URL:** `/teamdashptshots`
- **Data:** Same 6 tracking shot datasets at team level

### LeagueDashPlayerPtShot
- **Class:** `LeagueDashPlayerPtShot`
- **URL:** `/leaguedashplayerptshot`
- **Data:** League-wide player shooting with tracking filters (close def distance, dribbles, touch time, shot clock, shot distance, general range)
- **Columns:** FGA_FREQUENCY, FGM, FGA, FG_PCT, EFG_PCT, 2PT/3PT splits

### LeagueDashTeamPtShot
- **Class:** `LeagueDashTeamPtShot`
- **URL:** `/leaguedashteamptshot`
- **Data:** League-wide team shooting with same tracking filters

### LeagueDashOppPtShot
- **Class:** `LeagueDashOppPtShot`
- **URL:** `/leaguedashoppptshot`
- **Data:** Opponent shooting allowed (team defense), same tracking filters

---

## 4. CLUTCH STATS

### LeagueDashPlayerClutch
- **Class:** `LeagueDashPlayerClutch`
- **URL:** `/leaguedashplayerclutch`
- **Key Params:** AheadBehind, ClutchTime, PointDiff
- **Data:** Full player stats filtered to clutch situations
- **Columns:** All standard stats + ranks (GP, W, L, MIN, FGM/A/PCT, 3PT, FT, REB, AST, TOV, STL, BLK, PTS, PLUS_MINUS, DD2, TD3)

### LeagueDashTeamClutch
- **Class:** `LeagueDashTeamClutch`
- **URL:** `/leaguedashteamclutch`
- **Data:** Same clutch filtering at team level (57 columns + ranks)

### PlayerDashboardByClutch
- **Class:** `PlayerDashboardByClutch`
- **URL:** `/playerdashboardbyclutch`
- **Data:** Single player's clutch performance across 10+ time/score scenarios
- **Datasets:** last10sec_3pt, last10sec_3pt2, last1min_5pt, last3min_5pt, last5min_5pt (plus +/- variants), overall
- **Use cases:** Late-game performance analysis, closing ability

---

## 5. HUSTLE STATS

### BoxScoreHustleV2
- **Class:** `BoxScoreHustleV2`
- **URL:** `/boxscorehustlev2`
- **Data:** Per-game hustle metrics (player + team)
- **Metrics:** contestedShots (2pt/3pt), deflections, chargesDrawn, looseBallsRecovered (off/def), screenAssists, screenAssistPoints, boxOuts (off/def), boxOutPlayerRebounds

### HustleStatsBoxScore
- **Class:** `HustleStatsBoxScore`
- **URL:** `/hustlestatsboxscore`
- **Data:** Older format of per-game hustle stats
- **Datasets:** HustleStatsAvailable, PlayerStats, TeamStats

### LeagueHustleStatsPlayer
- **Class:** `LeagueHustleStatsPlayer`
- **URL:** `/leaguehustlestatsplayer`
- **Data:** Season-level hustle stats for all players (28 columns)
- **Key Metrics:** CONTESTED_SHOTS, CONTESTED_SHOTS_2PT/3PT, DEFLECTIONS, CHARGES_DRAWN, LOOSE_BALLS_RECOVERED (off/def + pct), SCREEN_ASSISTS, SCREEN_AST_PTS, BOX_OUTS (off/def + pct)

### LeagueHustleStatsTeam
- **Class:** `LeagueHustleStatsTeam`
- **URL:** `/leaguehustlestatsteam`
- **Data:** Season-level hustle stats for all teams

---

## 6. MATCHUP DATA

### BoxScoreMatchupsV3
- **Class:** `BoxScoreMatchupsV3`
- **URL:** `/boxscorematchupsv3`
- **Data:** Per-game offensive-defensive player matchup pairs
- **Key Columns:** personIdOff, personIdDef, matchupMinutes, switchesOn, playerPoints, teamPoints, FG/3PT/FT made/attempted/pct, matchupAssists, matchupTurnovers, matchupBlocks, helpBlocks, shootingFouls

### LeagueSeasonMatchups
- **Class:** `LeagueSeasonMatchups`
- **URL:** `/leagueseasonmatchups`
- **Data:** Season-long matchup stats between any off/def player pair
- **Columns:** OFF_PLAYER_ID/NAME, DEF_PLAYER_ID/NAME, GP, MATCHUP_MIN, PARTIAL_POSS, PLAYER_PTS, TEAM_PTS, MATCHUP_AST/TOV/BLK, MATCHUP_FGM/A/PCT, MATCHUP_FG3M/A/PCT, HELP_BLK, HELP_FGM/A/PCT, SFL
- **Use cases:** Head-to-head defensive assignments, who guards whom

### MatchupsRollup
- **Class:** `MatchupsRollup`
- **URL:** `/matchupsrollup`
- **Data:** Aggregated matchup data with position and time percentage
- **Columns:** POSITION, PERCENT_OF_TIME, DEF_PLAYER_ID/NAME, all matchup shooting/scoring stats

---

## 7. LINEUP STATS

### LeagueDashLineups
- **Class:** `LeagueDashLineups`
- **URL:** `/leaguedashlineups`
- **Key Param:** GroupQuantity (2-5 player combos)
- **Data:** Every lineup combination's stats league-wide
- **Columns:** GROUP_ID, GROUP_NAME, GP, W, L, MIN, full shooting/rebounding/scoring stats + ranks (57 cols)

### LeagueLineupViz
- **Class:** `LeagueLineupViz`
- **URL:** `/leaguelineupviz`
- **Data:** Lineup efficiency visualization data
- **Columns:** GROUP_ID, GROUP_NAME, MIN, OFF_RATING, DEF_RATING, NET_RATING, PACE, TS_PCT, FTA_RATE, TM_AST_PCT, PCT_FGA_2PT/3PT, PCT_PTS_2PT_MR/FB/FT/PAINT, OPP_FG3_PCT, OPP_EFG_PCT, OPP_FTA_RATE, OPP_TOV_PCT

### TeamDashLineups
- **Class:** `TeamDashLineups`
- **URL:** `/teamdashlineups`
- **Data:** Lineup combinations for a specific team
- **Datasets:** Lineups, Overall

---

## 8. ON/OFF COURT STATS

### TeamPlayerOnOffDetails
- **Class:** `TeamPlayerOnOffDetails`
- **URL:** `/teamplayeronoffdetails`
- **Data:** Full detailed stats when each player is on/off court
- **Datasets:**
  - `OverallTeamPlayerOnOffDetails` - team totals
  - `PlayersOnCourtTeamPlayerOnOffDetails` - stats with player ON
  - `PlayersOffCourtTeamPlayerOnOffDetails` - stats with player OFF
- **Columns:** VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS + full stat lines and ranks

### TeamPlayerOnOffSummary
- **Class:** `TeamPlayerOnOffSummary`
- **URL:** `/teamplayeronoffsummary`
- **Data:** Summary on/off impact (OFF_RATING, DEF_RATING, NET_RATING, PLUS_MINUS)
- **Datasets:** OverallTeamPlayerOnOffSummary (54 cols), PlayersOnCourt (13 cols), PlayersOffCourt (13 cols)

### LeaguePlayerOnDetails
- **Class:** `LeaguePlayerOnDetails`
- **URL:** `/leagueplayerondetails`
- **Data:** League-wide on-court player impact details
- **Columns:** VS_PLAYER_ID, VS_PLAYER_NAME, COURT_STATUS + full stats + ranks

---

## 9. PLAYER DASHBOARD ENDPOINTS

### PlayerDashboardByGeneralSplits
- **Class:** `PlayerDashboardByGeneralSplits`
- **URL:** `/playerdashboardbygeneralsplits`
- **Datasets:** DaysRestPlayerDashboard, LocationPlayerDashboard, MonthPlayerDashboard, OverallPlayerDashboard, PrePostAllStarPlayerDashboard, StartingPosition, WinsLossesPlayerDashboard
- **Columns:** 62 columns per dataset (full stats + ranks)

### PlayerDashboardByClutch
- **Class:** `PlayerDashboardByClutch`
- **URL:** `/playerdashboardbyclutch`
- **(See Clutch Stats section above)**

### PlayerDashboardByGameSplits
- **Class:** `PlayerDashboardByGameSplits`
- **URL:** `/playerdashboardbygamesplits`
- **Datasets:** ByActualMarginPlayerDashboard, ByHalfPlayerDashboard, ByPeriodPlayerDashboard, ByScoreMarginPlayerDashboard, OverallPlayerDashboard

### PlayerDashboardByLastNGames
- **Class:** `PlayerDashboardByLastNGames`
- **URL:** `/playerdashboardbylastngames`
- **Datasets:** GameNumberPlayerDashboard, Last5/10/15/20PlayerDashboard, OverallPlayerDashboard

### PlayerDashboardByShootingSplits
- **Class:** `PlayerDashboardByShootingSplits`
- **URL:** `/playerdashboardbyshootingsplits`
- **(See Shooting Splits section below)**

### PlayerDashboardByTeamPerformance
- **Class:** `PlayerDashboardByTeamPerformance`
- **URL:** `/playerdashboardbyteamperformance`
- **Datasets:** OverallPlayerDashboard, PointsScoredPlayerDashboard, PontsAgainstPlayerDashboard, ScoreDifferentialPlayerDashboard

### PlayerDashboardByYearOverYear
- **Class:** `PlayerDashboardByYearOverYear`
- **URL:** `/playerdashboardbyyearoveryear`
- **Datasets:** ByYearPlayerDashboard, OverallPlayerDashboard

---

## 10. TEAM DASHBOARD ENDPOINTS

### TeamDashboardByGeneralSplits
- **Class:** `TeamDashboardByGeneralSplits`
- **URL:** `/teamdashboardbygeneralsplits`
- **Datasets:** OverallTeamDashboard, MonthTeamDashboard, LocationTeamDashboard, DaysRestTeamDashboard, PrePostAllStarTeamDashboard, WinsLossesTeamDashboard

### TeamDashboardByShootingSplits
- **Class:** `TeamDashboardByShootingSplits`
- **URL:** `/teamdashboardbyshootingsplits`
- **(See Shooting Splits section below)**

### TeamPlayerDashboard
- **Class:** `TeamPlayerDashboard`
- **URL:** `/teamplayerdashboard`
- **Datasets:** PlayersSeasonTotals, TeamOverall

---

## 11. SHOOTING SPLITS

### PlayerDashboardByShootingSplits
- **Class:** `PlayerDashboardByShootingSplits`
- **URL:** `/playerdashboardbyshootingsplits`
- **Datasets:**
  - `AssistedBy` - who assisted the player's shots
  - `AssitedShotPlayerDashboard` - assisted vs unassisted
  - `OverallPlayerDashboard` - total shooting
  - `Shot5FTPlayerDashboard` - shots within 5 feet
  - `Shot8FTPlayerDashboard` - shots within 8 feet
  - `ShotAreaPlayerDashboard` - by court area
  - `ShotTypePlayerDashboard` - by shot type
  - `ShotTypeSummaryPlayerDashboard` - summary
- **Key Columns:** FGM, FGA, FG_PCT, EFG_PCT, PCT_AST_2PM, PCT_AST_3PM + ranks

### TeamDashboardByShootingSplits
- **Class:** `TeamDashboardByShootingSplits`
- **URL:** `/teamdashboardbyshootingsplits`
- **Datasets:** AssistedBy, AssitedShotTeamDashboard, OverallTeamDashboard, Shot5FT/8FTTeamDashboard, ShotAreaTeamDashboard, ShotTypeTeamDashboard

---

## 12. SYNERGY / PLAY TYPE DATA

### SynergyPlayTypes
- **Class:** `SynergyPlayTypes`
- **URL:** `/synergyplaytypes`
- **Key Params:** PlayerOrTeam (P/T), PlayType, TypeGrouping
- **Data:** Performance by play type classification
- **Columns:** PLAY_TYPE, TYPE_GROUPING, PERCENTILE, GP, POSS_PCT, PPP (points per possession), FG_PCT, FT_POSS_PCT, TOV_POSS_PCT, SF_POSS_PCT, PLUSONE_POSS_PCT, SCORE_POSS_PCT, EFG_PCT, POSS, PTS, FGM, FGA, FGMX
- **Play Types include:** Isolation, Pick & Roll Ball Handler, Pick & Roll Roll Man, Post Up, Spot Up, Handoff, Cut, Off Screen, Transition, Putbacks, Miscellaneous

---

## 13. DEFENSIVE TRACKING

### LeagueDashPtDefend
- **Class:** `LeagueDashPtDefend`
- **URL:** `/leaguedashptdefend`
- **Key Param:** DefenseCategory (Overall, 3 Pointers, 2 Pointers, Less Than 6Ft, Less Than 10Ft, Greater Than 15Ft)
- **Data:** Individual player defensive impact on opponent shooting
- **Columns:** CLOSE_DEF_PERSON_ID, PLAYER_NAME, GP, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

### LeagueDashPtTeamDefend
- **Class:** `LeagueDashPtTeamDefend`
- **URL:** `/leaguedashptteamdefend`
- **Data:** Team-level defensive impact by distance category
- **Columns:** TEAM_ID, TEAM_NAME, GP, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

### PlayerDashPtShotDefend
- **Class:** `PlayerDashPtShotDefend`
- **URL:** `/playerdashptshotdefend`
- **Data:** Individual player's defensive shot contest stats
- **Columns:** CLOSE_DEF_PERSON_ID, GP, DEFENSE_CATEGORY, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, PCT_PLUSMINUS

### BoxScoreDefensiveV2
- **Class:** `BoxScoreDefensiveV2`
- **URL:** `/boxscoredefensivev2`
- **Data:** Per-game defensive matchup box score
- **Key data:** Defensive matchup minutes, possessions, switches, points allowed, FG% allowed, 3PT% allowed, steals, blocks

### DefenseHub
- **Class:** `DefenseHub`
- **URL:** `/defensehub`
- **Data:** Defensive leaderboard hub (10 stat categories)
- **Stats:** DREB, STL, BLK, TM_DEF_RATING, OVERALL_PM, THREEP_DFGPCT, TWOP_DFGPCT, FIFTEENF_DFGPCT, DEF_RIM_PCT

---

## 14. PLAYER TRACKING - PASSES

### PlayerDashPtPass
- **Class:** `PlayerDashPtPass`
- **URL:** `/playerdashptpass`
- **Datasets:**
  - `PassesMade` - passes to each teammate (PASS_TO, PASS_TEAMMATE_PLAYER_ID, FREQUENCY, PASS, AST, FGM/A/PCT, 2PT/3PT splits)
  - `PassesReceived` - passes from each teammate (PASS_FROM, same stat columns)

### TeamDashPtPass
- **Class:** `TeamDashPtPass`
- **URL:** `/teamdashptpass`
- **Data:** Same pass tracking at team level (PassesMade, PassesReceived)

---

## 15. PLAYER TRACKING - REBOUNDS

### PlayerDashPtReb
- **Class:** `PlayerDashPtReb`
- **URL:** `/playerdashptreb`
- **Datasets:**
  - `NumContestedRebounding` - by contest level
  - `OverallRebounding` - aggregate
  - `RebDistanceRebounding` - by distance from basket
  - `ShotDistanceRebounding` - by original shot distance
  - `ShotTypeRebounding` - by shot type (2PT/3PT)
- **Key Columns:** OREB, DREB, REB, C_OREB/DREB/REB (contested), UC_OREB/DREB/REB (uncontested)

### TeamDashPtReb
- **Class:** `TeamDashPtReb`
- **URL:** `/teamdashptreb`
- **Data:** Same 5 rebound tracking datasets at team level

---

## 16. PLAYER TRACKING - SPEED/DISTANCE

### LeagueDashPtStats
- **Class:** `LeagueDashPtStats`
- **URL:** `/leaguedashptstats`
- **Key Param:** PtMeasureType = SpeedDistance | Rebounding | Possessions | CatchShoot | PullUpShot | Defense | Drives | Passing | ElbowTouch | PostTouch | PaintTouch | Efficiency
- **Data:** League-wide tracking stats by measure type
- **SpeedDistance Columns:** DIST_FEET, DIST_MILES, DIST_MILES_OFF, DIST_MILES_DEF, AVG_SPEED, AVG_SPEED_OFF, AVG_SPEED_DEF
- **Other PtMeasureTypes return different columns based on category**

### BoxScorePlayerTrackV3
- **Class:** `BoxScorePlayerTrackV3`
- **URL:** `/boxscoreplayertrackv3`
- **Data:** Per-game player tracking box score
- **Key Columns:** speed, distance, minutes, reboundChances (off/def), touches, secondaryAssists, freeThrowAssists, passes, contested/uncontested FG made/attempted, defended at rim stats

---

## 17. DRAFT COMBINE STATS

### DraftCombineStats
- **Class:** `DraftCombineStats`
- **URL:** `/draftcombinestats`
- **Data:** Complete combine data (48 columns) - measurements + shooting + athleticism

### DraftCombinePlayerAnthro
- **Class:** `DraftCombinePlayerAnthro`
- **URL:** `/draftcombineplayeranthro`
- **Data:** Physical measurements (18 columns)
- **Columns:** HEIGHT_WO_SHOES, HEIGHT_W_SHOES, WEIGHT, WINGSPAN, STANDING_REACH, BODY_FAT_PCT, HAND_LENGTH, HAND_WIDTH

### DraftCombineDrillResults
- **Class:** `DraftCombineDrillResults`
- **URL:** `/draftcombinedrillresults`
- **Data:** Athletic testing (12 columns)
- **Columns:** STANDING_VERTICAL_LEAP, MAX_VERTICAL_LEAP, LANE_AGILITY_TIME, MODIFIED_LANE_AGILITY_TIME, THREE_QUARTER_SPRINT, BENCH_PRESS

### DraftCombineSpotShooting
- **Class:** `DraftCombineSpotShooting`
- **URL:** `/draftcombinespotshooting`
- **Data:** Stationary shooting from 5 spots at 3 distances (54 columns)
- **Spots:** Corner Left, Break Left, Top Key, Break Right, Corner Right
- **Distances:** 15ft, College 3PT, NBA 3PT

### DraftCombineNonStationaryShooting
- **Class:** `DraftCombineNonStationaryShooting`
- **URL:** `/draftcombinenonstationaryshooting`
- **Data:** Off-dribble and on-move shooting drills

### DraftBoard
- **Class:** `DraftBoard`
- **URL:** `/draftboard`

### DraftHistory
- **Class:** `DraftHistory`
- **URL:** `/drafthistory`

---

## 18. WIN PROBABILITY / GAME FLOW

### WinProbabilityPBP
- **Class:** `WinProbabilityPBP`
- **URL:** `/winprobabilitypbp`
- **Key Params:** GameID, RunType
- **Datasets:**
  - `GameInfo` - game date, teams, final scores
  - `WinProbPBP` - HOME_PCT, VISITOR_PCT, HOME_PTS, VISITOR_PTS, HOME_SCORE_MARGIN, PERIOD, SECONDS_REMAINING, DESCRIPTION, LOCATION
- **Use cases:** Win probability charts, game flow visualization, leverage/pressure moments

---

## 19. BOX SCORE ENDPOINTS

### BoxScoreTraditionalV3 / V2
- **Class:** `BoxScoreTraditionalV3`
- **Data:** Standard box score (points, rebounds, assists, shooting, etc.)
- **Datasets:** PlayerStats, TeamStats, TeamStarterBenchStats

### BoxScoreAdvancedV3 / V2
- **Class:** `BoxScoreAdvancedV3`
- **Data:** Advanced metrics per game
- **Key Columns:** OFF_RATING, DEF_RATING, NET_RATING, AST_RATIO, OREB_PCT, DREB_PCT, TS_PCT, EFG_PCT, PACE, PIE (Player Impact Estimate)

### BoxScoreScoringV3 / V2
- **Class:** `BoxScoreScoringV3`
- **Data:** Scoring breakdown (2PT/3PT/FT distribution, assisted vs unassisted, paint/fastbreak/second-chance points)

### BoxScoreMiscV3 / V2
- **Class:** `BoxScoreMiscV3`
- **Data:** Miscellaneous stats (pointsOffTurnovers, pointsSecondChance, pointsFastBreak, pointsPaint, opponent equivalents, blocks against)

### BoxScoreFourFactorsV3 / V2
- **Class:** `BoxScoreFourFactorsV3`
- **Data:** Dean Oliver's Four Factors - EFG_PCT, FTA_RATE, TM_TOV_PCT, OREB_PCT + opponent versions

### BoxScoreUsageV3 / V2
- **Class:** `BoxScoreUsageV3`
- **Data:** Usage rates and percentage distributions (USG_PCT, PCT_FGM, PCT_AST, PCT_PTS, etc.)

### BoxScoreHustleV2
- **(See Hustle Stats section above)**

### BoxScoreMatchupsV3
- **(See Matchup Data section above)**

### BoxScoreDefensiveV2
- **(See Defensive Tracking section above)**

### BoxScorePlayerTrackV3
- **(See Player Tracking section above)**

### BoxScoreSummaryV2
- **Class:** `BoxScoreSummaryV2`
- **URL:** `/boxscoresummaryv2`
- **Datasets:**
  - `GameSummary` - date, status, teams, TV info
  - `LineScore` - quarter-by-quarter scoring
  - `Officials` - referee crew
  - `InactivePlayers` - DNP list
  - `GameInfo` - attendance, game time
  - `LastMeeting` - previous matchup result
  - `SeasonSeries` - season series record
  - `OtherStats` - PTS_PAINT, PTS_2ND_CHANCE, PTS_FB, LARGEST_LEAD, LEAD_CHANGES, TIMES_TIED, PTS_OFF_TO
  - `AvailableVideo` - video/tracking data availability flags

---

## 20. PLAY-BY-PLAY

### PlayByPlay / PlayByPlayV2 / PlayByPlayV3
- **Classes:** `PlayByPlay`, `PlayByPlayV2`, `PlayByPlayV3`
- **URLs:** `/playbyplay`, `/playbyplayv2`, `/playbyplayv3`
- **Data:** Every event in a game with timestamps, descriptions, player IDs, score

---

## 21. GAME ROTATION

### GameRotation
- **Class:** `GameRotation`
- **URL:** `/gamerotation`
- **Datasets:** AwayTeam, HomeTeam
- **Columns:** PERSON_ID, PLAYER_FIRST, PLAYER_LAST, IN_TIME_REAL, OUT_TIME_REAL, PLAYER_PTS, PT_DIFF, USG_PCT
- **Use cases:** Rotation/substitution pattern analysis, minutes distribution

---

## 22. ESTIMATED METRICS

### PlayerEstimatedMetrics
- **Class:** `PlayerEstimatedMetrics`
- **URL:** `/playerestimatedmetrics`
- **Data:** NBA's estimated advanced metrics for all players
- **Columns:** E_OFF_RATING, E_DEF_RATING, E_NET_RATING, E_AST_RATIO, E_OREB_PCT, E_DREB_PCT, E_REB_PCT, E_TOV_PCT, E_USG_PCT, E_PACE + ranks

### TeamEstimatedMetrics
- **Class:** `TeamEstimatedMetrics`
- **URL:** `/teamestimatedmetrics`
- **Data:** Same estimated metrics at team level

---

## 23. LEAGUE-WIDE STATS

### LeagueDashPlayerStats
- **Class:** `LeagueDashPlayerStats`
- **URL:** `/leaguedashplayerstats`
- **Key Param:** MeasureType (Base, Advanced, Misc, Four Factors, Scoring, Opponent, Usage, Defense)
- **Data:** All players' stats for a season with rich filtering (65 columns)

### LeagueDashTeamStats
- **Class:** `LeagueDashTeamStats`
- **URL:** `/leaguedashteamstats`
- **Data:** All teams' stats (53 columns), same MeasureType flexibility

### LeagueDashPlayerBioStats
- **Class:** `LeagueDashPlayerBioStats`
- **URL:** `/leaguedashplayerbiostats`
- **Data:** Player bio + performance (height, weight, college, draft info, NET_RATING, USG_PCT, TS_PCT, AST_PCT, etc.)

### LeagueLeaders
- **Class:** `LeagueLeaders`
- **URL:** `/leagueleaders`

### LeagueStandings / LeagueStandingsV3
- **Classes:** `LeagueStandings`, `LeagueStandingsV3`

---

## 24. PLAYER CAREER / PROFILE

### PlayerCareerStats
- **Class:** `PlayerCareerStats`
- **URL:** `/playercareerstats`
- **Datasets:** SeasonTotalsRegularSeason, SeasonTotalsPostSeason, SeasonTotalsAllStarSeason, SeasonTotalsCollegeSeason, CareerTotals (Regular/Post/AllStar/College), SeasonRankings (Regular/Post)

### PlayerProfileV2
- **Class:** `PlayerProfileV2`
- **URL:** `/playerprofilev2`
- **Datasets:** All of PlayerCareerStats + CareerHighs, SeasonHighs, NextGame, PreseasonTotals

### PlayerGameLog
- **Class:** `PlayerGameLog`
- **URL:** `/playergamelog`

### PlayerGameLogs
- **Class:** `PlayerGameLogs`
- **URL:** `/playergamelogs`

### PlayerAwards
- **Class:** `PlayerAwards`
- **URL:** `/playerawards`

### PlayerIndex
- **Class:** `PlayerIndex`
- **URL:** `/playerindex`

### CommonPlayerInfo
- **Class:** `CommonPlayerInfo`
- **URL:** `/commonplayerinfo`

### CommonAllPlayers
- **Class:** `CommonAllPlayers`
- **URL:** `/commonallplayers`

---

## 25. PLAYER / TEAM COMPARISON

### PlayerCompare
- **Class:** `PlayerCompare`
- **URL:** `/playercompare`
- **Datasets:** Individual, OverallCompare

### PlayerVsPlayer
- **Class:** `PlayerVsPlayer`
- **URL:** `/playervsplayer`
- **Datasets:** OnOffCourt, Overall, PlayerInfo, VsPlayerInfo, ShotAreaOnCourt/OffCourt/Overall, ShotDistanceOnCourt/OffCourt/Overall

### TeamAndPlayersVsPlayers
- **Class:** `TeamAndPlayersVsPlayers`
- **URL:** `/teamandplayersvsplayers`

### TeamVsPlayer
- **Class:** `TeamVsPlayer`
- **URL:** `/teamvsplayer`

---

## 26. GAME FINDERS / LOGS

### LeagueGameFinder
- **Class:** `LeagueGameFinder`
- **URL:** `/leaguegamefinder`
- **Data:** Search for games matching criteria (118 optional params!)
- **Filters:** Performance thresholds (PTS_GT, REB_GT, etc.), date ranges, teams, players, draft info
- **Columns:** SEASON_ID, TEAM_ID, GAME_ID, GAME_DATE, MATCHUP, WL, MIN, PTS, FGM/A/PCT, 3PT, FT, REB, AST, STL, BLK, TOV, PF, PLUS_MINUS

### LeagueGameLog
- **Class:** `LeagueGameLog`
- **URL:** `/leaguegamelog`

### PlayerGameStreakFinder
- **Class:** `PlayerGameStreakFinder`
- **URL:** `/playergamestreakfinder`

### TeamGameStreakFinder
- **Class:** `TeamGameStreakFinder`
- **URL:** `/teamgamestreakfinder`

### TeamGameLog
- **Class:** `TeamGameLog`
- **URL:** `/teamgamelog`

### TeamGameLogs
- **Class:** `TeamGameLogs`
- **URL:** `/teamgamelogs`

---

## 27. LEADERS & RANKINGS

### LeagueLeaders
- **Class:** `LeagueLeaders`
- **URL:** `/leagueleaders`

### AllTimeLeadersGrids
- **Class:** `AllTimeLeadersGrids`
- **URL:** `/alltimeleadersgrids`

### AssistLeaders
- **Class:** `AssistLeaders`
- **URL:** `/assistleaders`

### AssistTracker
- **Class:** `AssistTracker`
- **URL:** `/assisttracker`

### HomePageLeaders
- **Class:** `HomePageLeaders`
- **URL:** `/homepageleaders`

### HomePageV2
- **Class:** `HomePageV2`
- **URL:** `/homepagev2`

### LeadersTiles
- **Class:** `LeadersTiles`
- **URL:** `/leaderstiles`

### FranchiseLeaders
- **Class:** `FranchiseLeaders`
- **URL:** `/franchiseleaders`

### TeamHistoricalLeaders
- **Class:** `TeamHistoricalLeaders`
- **URL:** `/teamhistoricalleaders`

---

## 28. SCOREBOARD & SCHEDULE

### ScoreboardV2
- **Class:** `ScoreboardV2`
- **URL:** `/scoreboardv2`

### ScheduleLeagueV2 / ScheduleLeagueV2Int
- **Classes:** `ScheduleLeagueV2`, `ScheduleLeagueV2Int`

### ISTStandings
- **Class:** `ISTStandings`
- **URL:** `/iststandings` (In-Season Tournament)

---

## 29. REFERENCE / METADATA ENDPOINTS

### CommonAllPlayers
- **Class:** `CommonAllPlayers`

### CommonPlayerInfo
- **Class:** `CommonPlayerInfo`

### CommonPlayoffSeries
- **Class:** `CommonPlayoffSeries`

### CommonTeamRoster
- **Class:** `CommonTeamRoster`

### CommonTeamYears
- **Class:** `CommonTeamYears`

### TeamDetails
- **Class:** `TeamDetails`

### TeamInfoCommon
- **Class:** `TeamInfoCommon`

### TeamYearByYearStats
- **Class:** `TeamYearByYearStats`

### FranchiseHistory
- **Class:** `FranchiseHistory`

### FranchisePlayers
- **Class:** `FranchisePlayers`

### PlayoffPicture
- **Class:** `PlayoffPicture`

### PlayerCareerByCollege / PlayerCareerByCollegeRollup
- **Classes:** `PlayerCareerByCollege`, `PlayerCareerByCollegeRollup`

### PlayerNextNGames
- **Class:** `PlayerNextNGames`

---

## 30. VIDEO ENDPOINTS

### VideoDetails
- **Class:** `VideoDetails`
- **URL:** `/videodetails`

### VideoDetailsAsset
- **Class:** `VideoDetailsAsset`
- **URL:** `/videodetailsasset`

### VideoEvents
- **Class:** `VideoEvents`
- **URL:** `/videoevents`

### VideoStatus
- **Class:** `VideoStatus`
- **URL:** `/videostatus`

---

## 31. MISCELLANEOUS

### CumeStatsPlayer / CumeStatsPlayerGames
- **Classes:** `CumeStatsPlayer`, `CumeStatsPlayerGames`
- **Data:** Cumulative player stats

### CumeStatsTeam / CumeStatsTeamGames
- **Classes:** `CumeStatsTeam`, `CumeStatsTeamGames`
- **Data:** Cumulative team stats

### FantasyWidget
- **Class:** `FantasyWidget`
- **URL:** `/fantasywidget`

### InfographicFanDuelPlayer
- **Class:** `InfographicFanDuelPlayer`
- **URL:** `/infographicfanduelplayer`

### PlayerFantasyProfileBarGraph
- **Class:** `PlayerFantasyProfileBarGraph`
- **URL:** `/playerfantasyprofilebargraph`

### GLAlumBoxScoreSimilarityScore
- **Class:** `GLAlumBoxScoreSimilarityScore`
- **URL:** `/glalumboxscoresimilarityscore`

---

## COMPLETE ALPHABETICAL ENDPOINT LIST (All 135)

| # | Endpoint Class | URL Path |
|---|---------------|----------|
| 1 | AllTimeLeadersGrids | /alltimeleadersgrids |
| 2 | AssistLeaders | /assistleaders |
| 3 | AssistTracker | /assisttracker |
| 4 | BoxScoreAdvancedV2 | /boxscoreadvancedv2 |
| 5 | BoxScoreAdvancedV3 | /boxscoreadvancedv3 |
| 6 | BoxScoreDefensiveV2 | /boxscoredefensivev2 |
| 7 | BoxScoreFourFactorsV2 | /boxscorefourfactorsv2 |
| 8 | BoxScoreFourFactorsV3 | /boxscorefourfactorsv3 |
| 9 | BoxScoreHustleV2 | /boxscorehustlev2 |
| 10 | BoxScoreMatchupsV3 | /boxscorematchupsv3 |
| 11 | BoxScoreMiscV2 | /boxscoremiscv2 |
| 12 | BoxScoreMiscV3 | /boxscoremiscv3 |
| 13 | BoxScorePlayerTrackV3 | /boxscoreplayertrackv3 |
| 14 | BoxScoreScoringV2 | /boxscorescoringv2 |
| 15 | BoxScoreScoringV3 | /boxscorescoringv3 |
| 16 | BoxScoreSummaryV2 | /boxscoresummaryv2 |
| 17 | BoxScoreSummaryV3 | /boxscoresummaryv3 |
| 18 | BoxScoreTraditionalV2 | /boxscoretraditionalv2 |
| 19 | BoxScoreTraditionalV3 | /boxscoretraditionalv3 |
| 20 | BoxScoreUsageV2 | /boxscoreusagev2 |
| 21 | BoxScoreUsageV3 | /boxscoreusagev3 |
| 22 | CommonAllPlayers | /commonallplayers |
| 23 | CommonPlayerInfo | /commonplayerinfo |
| 24 | CommonPlayoffSeries | /commonplayoffseries |
| 25 | CommonTeamRoster | /commonteamroster |
| 26 | CommonTeamYears | /commonteamyears |
| 27 | CumeStatsPlayer | /cumestatsplayer |
| 28 | CumeStatsPlayerGames | /cumestatsplayergames |
| 29 | CumeStatsTeam | /cumestatsteam |
| 30 | CumeStatsTeamGames | /cumestatsteamgames |
| 31 | DefenseHub | /defensehub |
| 32 | DraftBoard | /draftboard |
| 33 | DraftCombineDrillResults | /draftcombinedrillresults |
| 34 | DraftCombineNonStationaryShooting | /draftcombinenonstationaryshooting |
| 35 | DraftCombinePlayerAnthro | /draftcombineplayeranthro |
| 36 | DraftCombineSpotShooting | /draftcombinespotshooting |
| 37 | DraftCombineStats | /draftcombinestats |
| 38 | DraftHistory | /drafthistory |
| 39 | FantasyWidget | /fantasywidget |
| 40 | FranchiseHistory | /franchisehistory |
| 41 | FranchiseLeaders | /franchiseleaders |
| 42 | FranchisePlayers | /franchiseplayers |
| 43 | GameRotation | /gamerotation |
| 44 | GLAlumBoxScoreSimilarityScore | /glalumboxscoresimilarityscore |
| 45 | HomePageLeaders | /homepageleaders |
| 46 | HomePageV2 | /homepagev2 |
| 47 | HustleStatsBoxScore | /hustlestatsboxscore |
| 48 | InfographicFanDuelPlayer | /infographicfanduelplayer |
| 49 | ISTStandings | /iststandings |
| 50 | LeadersTiles | /leaderstiles |
| 51 | LeagueDashLineups | /leaguedashlineups |
| 52 | LeagueDashOppPtShot | /leaguedashoppptshot |
| 53 | LeagueDashPlayerBioStats | /leaguedashplayerbiostats |
| 54 | LeagueDashPlayerClutch | /leaguedashplayerclutch |
| 55 | LeagueDashPlayerPtShot | /leaguedashplayerptshot |
| 56 | LeagueDashPlayerShotLocations | /leaguedashplayershotlocations |
| 57 | LeagueDashPlayerStats | /leaguedashplayerstats |
| 58 | LeagueDashPtDefend | /leaguedashptdefend |
| 59 | LeagueDashPtStats | /leaguedashptstats |
| 60 | LeagueDashPtTeamDefend | /leaguedashptteamdefend |
| 61 | LeagueDashTeamClutch | /leaguedashteamclutch |
| 62 | LeagueDashTeamPtShot | /leaguedashteamptshot |
| 63 | LeagueDashTeamShotLocations | /leaguedashteamshotlocations |
| 64 | LeagueDashTeamStats | /leaguedashteamstats |
| 65 | LeagueGameFinder | /leaguegamefinder |
| 66 | LeagueGameLog | /leaguegamelog |
| 67 | LeagueHustleStatsPlayer | /leaguehustlestatsplayer |
| 68 | LeagueHustleStatsTeam | /leaguehustlestatsteam |
| 69 | LeagueLeaders | /leagueleaders |
| 70 | LeagueLineupViz | /leaguelineupviz |
| 71 | LeaguePlayerOnDetails | /leagueplayerondetails |
| 72 | LeagueSeasonMatchups | /leagueseasonmatchups |
| 73 | LeagueStandings | /leaguestandings |
| 74 | LeagueStandingsV3 | /leaguestandingsv3 |
| 75 | MatchupsRollup | /matchupsrollup |
| 76 | PlayByPlay | /playbyplay |
| 77 | PlayByPlayV2 | /playbyplayv2 |
| 78 | PlayByPlayV3 | /playbyplayv3 |
| 79 | PlayerAwards | /playerawards |
| 80 | PlayerCareerByCollege | /playercareerbycollege |
| 81 | PlayerCareerByCollegeRollup | /playercareerbycollegerollup |
| 82 | PlayerCareerStats | /playercareerstats |
| 83 | PlayerCompare | /playercompare |
| 84 | PlayerDashboardByClutch | /playerdashboardbyclutch |
| 85 | PlayerDashboardByGameSplits | /playerdashboardbygamesplits |
| 86 | PlayerDashboardByGeneralSplits | /playerdashboardbygeneralsplits |
| 87 | PlayerDashboardByLastNGames | /playerdashboardbylastngames |
| 88 | PlayerDashboardByShootingSplits | /playerdashboardbyshootingsplits |
| 89 | PlayerDashboardByTeamPerformance | /playerdashboardbyteamperformance |
| 90 | PlayerDashboardByYearOverYear | /playerdashboardbyyearoveryear |
| 91 | PlayerDashPtPass | /playerdashptpass |
| 92 | PlayerDashPtReb | /playerdashptreb |
| 93 | PlayerDashPtShotDefend | /playerdashptshotdefend |
| 94 | PlayerDashPtShots | /playerdashptshots |
| 95 | PlayerEstimatedMetrics | /playerestimatedmetrics |
| 96 | PlayerFantasyProfileBarGraph | /playerfantasyprofilebargraph |
| 97 | PlayerGameLog | /playergamelog |
| 98 | PlayerGameLogs | /playergamelogs |
| 99 | PlayerGameStreakFinder | /playergamestreakfinder |
| 100 | PlayerIndex | /playerindex |
| 101 | PlayerNextNGames | /playernextngames |
| 102 | PlayerProfileV2 | /playerprofilev2 |
| 103 | PlayerVsPlayer | /playervsplayer |
| 104 | PlayoffPicture | /playoffpicture |
| 105 | ScheduleLeagueV2 | /scheduleleaguev2 |
| 106 | ScheduleLeagueV2Int | /scheduleleaguev2int |
| 107 | ScoreboardV2 | /scoreboardv2 |
| 108 | ShotChartDetail | /shotchartdetail |
| 109 | ShotChartLeagueWide | /shotchartleaguewide |
| 110 | ShotChartLineupDetail | /shotchartlineupdetail |
| 111 | SynergyPlayTypes | /synergyplaytypes |
| 112 | TeamAndPlayersVsPlayers | /teamandplayersvsplayers |
| 113 | TeamDashboardByGeneralSplits | /teamdashboardbygeneralsplits |
| 114 | TeamDashboardByShootingSplits | /teamdashboardbyshootingsplits |
| 115 | TeamDashLineups | /teamdashlineups |
| 116 | TeamDashPtPass | /teamdashptpass |
| 117 | TeamDashPtReb | /teamdashptreb |
| 118 | TeamDashPtShots | /teamdashptshots |
| 119 | TeamDetails | /teamdetails |
| 120 | TeamEstimatedMetrics | /teamestimatedmetrics |
| 121 | TeamGameLog | /teamgamelog |
| 122 | TeamGameLogs | /teamgamelogs |
| 123 | TeamGameStreakFinder | /teamgamestreakfinder |
| 124 | TeamHistoricalLeaders | /teamhistoricalleaders |
| 125 | TeamInfoCommon | /teaminfocommon |
| 126 | TeamPlayerDashboard | /teamplayerdashboard |
| 127 | TeamPlayerOnOffDetails | /teamplayeronoffdetails |
| 128 | TeamPlayerOnOffSummary | /teamplayeronoffsummary |
| 129 | TeamVsPlayer | /teamvsplayer |
| 130 | TeamYearByYearStats | /teamyearbyyearstats |
| 131 | VideoDetails | /videodetails |
| 132 | VideoDetailsAsset | /videodetailsasset |
| 133 | VideoEvents | /videoevents |
| 134 | VideoStatus | /videostatus |
| 135 | WinProbabilityPBP | /winprobabilitypbp |
