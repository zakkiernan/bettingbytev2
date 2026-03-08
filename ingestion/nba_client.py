import time
from nba_api.stats.endpoints import (
    scoreboardv3,
    boxscoreadvancedv3,
    boxscoreplayertrackv3,
    leaguedashteamstats,
    leaguedashptdefend
)
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard, boxscore as live_boxscore
from nba_api.stats.static import players, teams
from datetime import date
import unicodedata


RATE_LIMIT_DELAY = 1

from datetime import date

def get_todays_games(game_date=None):
    """
    Returns a list of games for the given date (defaults to today).
    Used for matching FanDuel events to real NBA game IDs.
    """
    try:
        from datetime import date
        if game_date is None:
            game_date = date.today()
        formatted = game_date.strftime("%m/%d/%Y")

        board = scoreboardv3.ScoreboardV3(game_date=formatted)
        time.sleep(RATE_LIMIT_DELAY)
        data = board.get_dict()

        team_list = teams.get_teams()
        team_map = {str(t['id']): t['full_name'].lower() for t in team_list}

        games = []
        for game in data['scoreboard']['games']:
            home_id = str(game['homeTeam']['teamId'])
            away_id = str(game['awayTeam']['teamId'])
            games.append({
                'game_id': game['gameId'],
                'home_team_id': home_id,
                'away_team_id': away_id,
                'home_team_name': team_map.get(home_id, ''),
                'away_team_name': team_map.get(away_id, ''),
                'game_status': game['gameStatus'],
            })
        return games

    except Exception as e:
        print(f"Error fetching games for {game_date}: {e}")
        return []
    
def get_player_id_map():
    """
    Returns a dict of {player_name: player_id} for all NBA players.
    Includes accent-stripped versions to match FanDuel's plain ASCII names.
    """
    def strip_accents(name):
        return ''.join(
            c for c in unicodedata.normalize('NFD', name)
            if unicodedata.category(c) != 'Mn'
        )

    player_list = players.get_players()
    player_map = {}

    for player in player_list:
        full_name = player['full_name']
        player_id = str(player['id'])
        player_map[full_name] = player_id
        # Also store accent-stripped version
        stripped = strip_accents(full_name)
        if stripped != full_name:
            player_map[stripped] = player_id

    return player_map

def get_live_scoreboard():
    """
    Returns all games currently in progress with live scores and game clock.
    """
    try:
        board = live_scoreboard.ScoreBoard()
        time.sleep(RATE_LIMIT_DELAY)
        data = board.get_dict()

        live_games = []
        for game in data['scoreboard']['games']:
            live_games.append({
                'game_id': game['gameId'],
                'home_team_id': str(game['homeTeam']['teamId']),
                'away_team_id': str(game['awayTeam']['teamId']),
                'home_team_score': game['homeTeam']['score'],
                'away_team_score': game['awayTeam']['score'],
                'period': game['period'],
                'game_clock': game['gameClock'],
                'game_status': game['gameStatus'],
            })
        return live_games

    except Exception as e:
        print(f"Error fetching live scoreboard: {e}")
        return []
    
def get_live_boxscore(game_id):
    """
    Returns real-time player stats for a game in progress.
    """
    try:
        box = live_boxscore.BoxScore(game_id=game_id)
        time.sleep(RATE_LIMIT_DELAY)
        data = box.get_dict()

        players_data = []
        for team in ['homeTeam', 'awayTeam']:
            team_data = data['game'][team]
            for player in team_data['players']:
                stats = player['statistics']
                players_data.append({
                    'player_id': str(player['personId']),
                    'player_name': player['name'],
                    'team_id': str(team_data['teamId']),
                    'minutes': stats['minutesCalculated'],
                    'points': stats['points'],
                    'rebounds': stats['reboundsTotal'],
                    'assists': stats['assists'],
                    'steals': stats['steals'],
                    'blocks': stats['blocks'],
                    'turnovers': stats['turnovers'],
                    'field_goals_made': stats['fieldGoalsMade'],
                    'field_goals_attempted': stats['fieldGoalsAttempted'],
                    'threes_made': stats['threePointersMade'],
                    'threes_attempted': stats['threePointersAttempted'],
                    'free_throws_made': stats['freeThrowsMade'],
                    'free_throws_attempted': stats['freeThrowsAttempted'],
                    'fouls': stats['foulsPersonal'],
                    'plus_minus': stats['plusMinusPoints'],
                    'on_court': player['oncourt'],
                    'starter': player['starter'],
                })
        return players_data

    except Exception as e:
        print(f"Error fetching live boxscore for game {game_id}: {e}")
        return []
    
def get_advanced_boxscore(game_id):
    """
    Returns advanced stats for a completed game.
    Feeds HistoricalAdvancedLog - usage, pace, ratings.
    """
    try:
        box = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id)
        time.sleep(RATE_LIMIT_DELAY)
        data = box.get_dict()

        players_data = []
        for player in data['boxScoreAdvanced']['playerStats']:
            players_data.append({
                'player_id': str(player['personId']),
                'player_name': f"{player['firstName']} {player['familyName']}",
                'game_id': player['gameId'],
                'usage_percentage': player['usagePercentage'],
                'estimated_usage_percentage': player['estimatedUsagePercentage'],
                'pace': player['pace'],
                'pace_per40': player['pacePer40'],
                'possessions': player['possessions'],
                'offensive_rating': player['offensiveRating'],
                'defensive_rating': player['defensiveRating'],
                'net_rating': player['netRating'],
                'true_shooting_percentage': player['trueShootingPercentage'],
                'effective_field_goal_percentage': player['effectiveFieldGoalPercentage'],
                'assist_percentage': player['assistPercentage'],
                'assist_to_turnover': player['assistToTurnover'],
                'offensive_rebound_percentage': player['offensiveReboundPercentage'],
                'defensive_rebound_percentage': player['defensiveReboundPercentage'],
                'pie': player['PIE'],
            })
        return players_data

    except Exception as e:
        print(f"Error fetching advanced boxscore for game {game_id}: {e}")
        return []
    
def get_player_tracking(game_id):
    """
    Returns player tracking data for a completed game.
    Feeds HistoricalAdvancedLog - touches, speed, distance.
    """
    try:
        box = boxscoreplayertrackv3.BoxScorePlayerTrackV3(game_id=game_id)
        time.sleep(RATE_LIMIT_DELAY)
        data = box.get_dict()

        players_data = []
        for player in data['boxScorePlayerTrack']['playerStats']:
            players_data.append({
                'player_id': str(player['personId']),
                'game_id': player['gameId'],
                'speed': player['speed'],
                'distance': player['distance'],
                'touches': player['touches'],
                'passes': player['passes'],
                'secondary_assists': player['secondaryAssists'],
                'free_throw_assists': player['freeThrowAssists'],
                'rebound_chances_offensive': player['reboundChancesOffensive'],
                'rebound_chances_defensive': player['reboundChancesDefensive'],
                'rebound_chances_total': player['reboundChancesTotal'],
                'contested_field_goals_made': player['contestedFieldGoalsMade'],
                'contested_field_goals_attempted': player['contestedFieldGoalsAttempted'],
                'uncontested_field_goals_made': player['uncontestedFieldGoalsMade'],
                'uncontested_field_goals_attempted': player['uncontestedFieldGoalsAttempted'],
                'defended_at_rim_field_goals_made': player['defendedAtRimFieldGoalsMade'],
                'defended_at_rim_field_goals_attempted': player['defendedAtRimFieldGoalsAttempted'],
            })
        return players_data

    except Exception as e:
        print(f"Error fetching player tracking for game {game_id}: {e}")
        return []
    
def get_team_defensive_stats(season="2025-26"):
    """
    Returns team defensive ratings and shot zone defense data.
    Feeds TeamDefensiveStat table. Run once daily before games.
    """
    try:
        team_stats = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_simple_nullable="Defense"
        )
        time.sleep(RATE_LIMIT_DELAY)
        data = team_stats.get_dict()

        defensive_data = {}
        for team in data['resultSets'][0]['rowSet']:
            team_id = str(team[0])
            defensive_data[team_id] = {
                'team_id': team_id,
                'team_name': team[1],
                'season': season,
                'defensive_rating': team[9],
                'opponent_pace': team[10],
                'points_allowed_per_game': team[26],
                'opponent_field_goal_percentage': team[11],
                'opponent_three_point_percentage': team[14],
            }

        pt_defend = leaguedashptdefend.LeagueDashPtDefend(
            season=season,
            defense_category_nullable="Overall"
        )
        time.sleep(RATE_LIMIT_DELAY)
        pt_data = pt_defend.get_dict()

        for row in pt_data['resultSets'][0]['rowSet']:
            team_id = str(row[0])
            if team_id in defensive_data:
                defensive_data[team_id].update({
                    'd_fg_pct_overall': row[6],
                    'd_pct_plusminus_overall': row[8],
                })

        return list(defensive_data.values())

    except Exception as e:
        print(f"Error fetching team defensive stats: {e}")
        return []