from datetime import datetime
from database.models import PlayerPropSnapshot, OddsSnapshot, HistoricalGameLog, HistoricalAdvancedLog, TeamDefensiveStat
from database.db import SessionLocal

def write_prop_snapshot(props: list, is_live: bool = False):
    """
    Writes current prop lines to PlayerPropSnapshot.
    Upserts - updates existing records or inserts new ones.
    """
    if not props:
        return

    db = SessionLocal()
    try:
        for prop in props:
            existing = db.query(PlayerPropSnapshot).filter(
                PlayerPropSnapshot.game_id == prop['game_id'],
                PlayerPropSnapshot.player_id == prop['player_id'],
                PlayerPropSnapshot.stat_type == prop['stat_type'],
                PlayerPropSnapshot.is_live == is_live
            ).first()

            if existing:
                existing.line = prop['line']
                existing.over_odds = prop['over_odds']
                existing.under_odds = prop['under_odds']
                existing.captured_at = prop['captured_at']
            else:
                snapshot = PlayerPropSnapshot(
                    game_id=prop['game_id'],
                    player_id=prop['player_id'],
                    player_name=prop['player_name'],
                    stat_type=prop['stat_type'],
                    line=prop['line'],
                    over_odds=prop['over_odds'],
                    under_odds=prop['under_odds'],
                    is_live=is_live,
                    captured_at=prop['captured_at']
                )
                db.add(snapshot)

        db.commit()
        print(f"Wrote {len(props)} prop snapshots")

    except Exception as e:
        db.rollback()
        print(f"Error writing prop snapshots: {e}")
    finally:
        db.close()

def write_odds_snapshot(props: list):
    """
    Writes a new odds record for every prop on every poll cycle.
    Never updates - always inserts. Builds line movement history.
    """
    if not props:
        return

    db = SessionLocal()
    try:
        for prop in props:
            snapshot = OddsSnapshot(
                game_id=prop['game_id'],
                player_id=prop['player_id'],
                player_name=prop['player_name'],
                stat_type=prop['stat_type'],
                line=prop['line'],
                over_odds=prop['over_odds'],
                under_odds=prop['under_odds'],
                source="fanduel",
                captured_at=prop['captured_at']
            )
            db.add(snapshot)

        db.commit()
        print(f"Wrote {len(props)} odds snapshots")

    except Exception as e:
        db.rollback()
        print(f"Error writing odds snapshots: {e}")
    finally:
        db.close()

def write_historical_game_log(game_logs: list):
    """
    Writes completed game box scores to HistoricalGameLog.
    Skips records that already exist for the same game/player combination.
    """
    if not game_logs:
        return

    db = SessionLocal()
    try:
        for log in game_logs:
            existing = db.query(HistoricalGameLog).filter(
                HistoricalGameLog.game_id == log['game_id'],
                HistoricalGameLog.player_id == log['player_id']
            ).first()

            if existing:
                continue

            game_log = HistoricalGameLog(
                game_id=log['game_id'],
                game_date=log.get('game_date', datetime.utcnow()),
                player_id=log['player_id'],
                player_name=log['player_name'],
                team=log['team'],
                opponent=log['opponent'],
                is_home=log['is_home'],
                minutes=log.get('minutes'),
                points=log.get('points'),
                rebounds=log.get('rebounds'),
                assists=log.get('assists'),
                steals=log.get('steals'),
                blocks=log.get('blocks'),
                turnovers=log.get('turnovers'),
                threes_made=log.get('threes_made'),
                threes_attempted=log.get('threes_attempted'),
                field_goals_made=log.get('field_goals_made'),
                field_goals_attempted=log.get('field_goals_attempted'),
                free_throws_made=log.get('free_throws_made'),
                free_throws_attempted=log.get('free_throws_attempted'),
                fantasy_points=log.get('fantasy_points'),
            )
            db.add(game_log)

        db.commit()
        print(f"Wrote {len(game_logs)} game logs")

    except Exception as e:
        db.rollback()
        print(f"Error writing game logs: {e}")
    finally:
        db.close()

def write_advanced_log(advanced_logs: list):
    """
    Writes advanced and tracking stats to HistoricalAdvancedLog.
    Merges data from BoxScoreAdvancedV3 and BoxScorePlayerTrackV3.
    """
    if not advanced_logs:
        return

    db = SessionLocal()
    try:
        for log in advanced_logs:
            existing = db.query(HistoricalAdvancedLog).filter(
                HistoricalAdvancedLog.game_id == log['game_id'],
                HistoricalAdvancedLog.player_id == log['player_id']
            ).first()

            if existing:
                # Update tracking fields if they were missing
                for field in ['speed', 'distance', 'touches', 'passes',
                              'secondary_assists', 'free_throw_assists',
                              'rebound_chances_offensive', 'rebound_chances_defensive',
                              'rebound_chances_total', 'contested_field_goals_made',
                              'contested_field_goals_attempted']:
                    if getattr(existing, field) is None and log.get(field) is not None:
                        setattr(existing, field, log[field])
                continue

            advanced_log = HistoricalAdvancedLog(
                game_id=log['game_id'],
                player_id=log['player_id'],
                usage_percentage=log.get('usage_percentage'),
                estimated_usage_percentage=log.get('estimated_usage_percentage'),
                pace=log.get('pace'),
                pace_per40=log.get('pace_per40'),
                possessions=log.get('possessions'),
                offensive_rating=log.get('offensive_rating'),
                defensive_rating=log.get('defensive_rating'),
                net_rating=log.get('net_rating'),
                true_shooting_percentage=log.get('true_shooting_percentage'),
                effective_field_goal_percentage=log.get('effective_field_goal_percentage'),
                assist_percentage=log.get('assist_percentage'),
                assist_to_turnover=log.get('assist_to_turnover'),
                offensive_rebound_percentage=log.get('offensive_rebound_percentage'),
                defensive_rebound_percentage=log.get('defensive_rebound_percentage'),
                pie=log.get('pie'),
                speed=log.get('speed'),
                distance=log.get('distance'),
                touches=log.get('touches'),
                passes=log.get('passes'),
                secondary_assists=log.get('secondary_assists'),
                free_throw_assists=log.get('free_throw_assists'),
                rebound_chances_offensive=log.get('rebound_chances_offensive'),
                rebound_chances_defensive=log.get('rebound_chances_defensive'),
                rebound_chances_total=log.get('rebound_chances_total'),
                contested_field_goals_made=log.get('contested_field_goals_made'),
                contested_field_goals_attempted=log.get('contested_field_goals_attempted'),
                uncontested_field_goals_made=log.get('uncontested_field_goals_made'),
                uncontested_field_goals_attempted=log.get('uncontested_field_goals_attempted'),
                defended_at_rim_field_goals_made=log.get('defended_at_rim_field_goals_made'),
                defended_at_rim_field_goals_attempted=log.get('defended_at_rim_field_goals_attempted'),
            )
            db.add(advanced_log)

        db.commit()
        print(f"Wrote {len(advanced_logs)} advanced logs")

    except Exception as e:
        db.rollback()
        print(f"Error writing advanced logs: {e}")
    finally:
        db.close()

def write_team_defensive_stats(defensive_stats: list):
    """
    Upserts team defensive stats. Run once daily.
    """
    if not defensive_stats:
        return

    db = SessionLocal()
    try:
        for stat in defensive_stats:
            existing = db.query(TeamDefensiveStat).filter(
                TeamDefensiveStat.team_id == stat['team_id'],
                TeamDefensiveStat.season == stat['season']
            ).first()

            if existing:
                for field, value in stat.items():
                    if field not in ['team_id', 'season']:
                        setattr(existing, field, value)
            else:
                team_stat = TeamDefensiveStat(**stat)
                db.add(team_stat)

        db.commit()
        print(f"Wrote {len(defensive_stats)} team defensive stats")

    except Exception as e:
        db.rollback()
        print(f"Error writing team defensive stats: {e}")
    finally:
        db.close()