import time
from apscheduler.schedulers.background import BackgroundScheduler
from ingestion.nba_client import (
    get_live_scoreboard,
    get_advanced_boxscore,
    get_player_tracking,
    get_team_defensive_stats
)
from ingestion.fanduel_client import scrape_props
from ingestion.writer import (
    write_prop_snapshot,
    write_odds_snapshot,
    write_advanced_log,
    write_team_defensive_stats
)

# Game status codes from NBA API
STATUS_SCHEDULED = 1
STATUS_LIVE = 2
STATUS_FINISHED = 3

def get_current_mode():
    """
    Checks live scoreboard and returns current operating mode.
    Returns 'live', 'pregame', 'postgame', or 'idle'.
    """
    games = get_live_scoreboard()

    if not games:
        return 'idle'

    statuses = [game['game_status'] for game in games]

    if STATUS_LIVE in statuses:
        return 'live'

    if all(s == STATUS_FINISHED for s in statuses):
        return 'postgame'

    if all(s == STATUS_SCHEDULED for s in statuses):
        return 'pregame'

    # Mix of scheduled and finished - some games done, others not started
    # If any are still scheduled, treat as pregame
    if STATUS_SCHEDULED in statuses:
        return 'pregame'

    return 'idle'

def run_pregame_cycle():
    """
    Pre-game polling cycle. Runs every 5 minutes.
    Fetches prop lines and tracks early line movement.
    """
    print("Running pre-game cycle...")
    props = scrape_props()
    if props:
        write_prop_snapshot(props, is_live=False)
        write_odds_snapshot(props)

def run_live_cycle():
    """
    Live game polling cycle. Runs every 30 seconds.
    Fetches live prop lines and live box scores.
    """
    print("Running live cycle...")

    # Fetch and write live props
    props = scrape_props()
    if props:
        write_prop_snapshot(props, is_live=True)
        write_odds_snapshot(props)

def run_postgame_cycle():
    """
    Post-game cycle. Runs once after all games finish.
    Writes final box scores and advanced stats to historical tables.
    """
    print("Running post-game cycle...")

    games = get_live_scoreboard()
    finished_games = [
        g for g in games
        if g['game_status'] == STATUS_FINISHED
    ]

    for game in finished_games:
        game_id = game['game_id']
        print(f"Processing finished game: {game_id}")

        # Advanced box score
        advanced_logs = get_advanced_boxscore(game_id)
        if advanced_logs:
            write_advanced_log(advanced_logs)

        # Player tracking
        tracking_logs = get_player_tracking(game_id)
        if tracking_logs:
            write_advanced_log(tracking_logs)

        time.sleep(1)

def run_daily_setup():
    """
    Runs once per day in the morning.
    Updates team defensive stats for the pre-game model.
    """
    print("Running daily setup...")
    defensive_stats = get_team_defensive_stats()
    if defensive_stats:
        write_team_defensive_stats(defensive_stats)

# Track whether postgame has already run tonight
_postgame_complete = False

def run_scheduler_cycle():
    """
    Master cycle called every 30 seconds.
    Checks current mode and dispatches to appropriate handler.
    """
    global _postgame_complete

    mode = get_current_mode()
    print(f"Scheduler mode: {mode}")

    if mode == 'idle':
        return

    if mode == 'live':
        _postgame_complete = False
        run_live_cycle()

    elif mode == 'pregame':
        _postgame_complete = False
        run_pregame_cycle()

    elif mode == 'postgame':
        if not _postgame_complete:
            run_postgame_cycle()
            _postgame_complete = True
            print("Post-game cycle complete for tonight")

def start_scheduler():
    """
    Initializes and starts the background scheduler.
    Called once at application startup.
    """
    scheduler = BackgroundScheduler()

    # Master cycle - every 30 seconds
    scheduler.add_job(
        run_scheduler_cycle,
        'interval',
        seconds=30,
        id='master_cycle'
    )

    # Daily setup - every morning at 9am
    scheduler.add_job(
        run_daily_setup,
        'cron',
        hour=9,
        minute=0,
        id='daily_setup'
    )

    scheduler.start()
    print("Scheduler started")
    return scheduler