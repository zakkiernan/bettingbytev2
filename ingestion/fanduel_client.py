import httpx
import time
from datetime import datetime
from ingestion.nba_client import get_todays_games, get_player_id_map

FANDUEL_COMPETITION_URL = "https://api.sportsbook.fanduel.com/sbapi/competition-page"
FANDUEL_EVENT_URL = "https://api.sportsbook.fanduel.com/sbapi/event-page"
FANDUEL_AK = "FhMFpcPWXMeyZxOx"
FANDUEL_COMPETITION_ID = 10547864
FANDUEL_EVENT_TYPE_ID = 7522

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": "NY",
}

PROP_TABS = {
    "points": "player-points",
    "rebounds": "player-rebounds",
    "assists": "player-assists",
    "threes": "player-threes",
}

STAT_TYPE_MAP = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "Threes": "threes",
    "3-Pointers": "threes",
    "Three Pointers": "threes",
}

def fetch_nba_events():
    """
    Step 1 - Get today's NBA event IDs and names from FanDuel.
    Returns list of {eventId, name} dicts.
    """
    try:
        response = httpx.get(
            FANDUEL_COMPETITION_URL,
            params={
                "_ak": FANDUEL_AK,
                "eventTypeId": str(FANDUEL_EVENT_TYPE_ID),
                "competitionId": str(FANDUEL_COMPETITION_ID),
                "tabId": "SCHEDULE",
            },
            headers=HEADERS,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        events = data.get('attachments', {}).get('events', {})
        result = []
        for event_id, event in events.items():
            result.append({
                'eventId': event['eventId'],
                'name': event.get('name', '').lower()
            })

        print(f"Found {len(result)} NBA events on FanDuel")
        return result

    except Exception as e:
        print(f"Error fetching NBA events: {e}")
        return []

def fetch_event_props(event_id, stat_key):
    """
    Step 2 - Get prop markets for one game and one stat type.
    """
    tab = PROP_TABS.get(stat_key)
    if not tab:
        return None

    try:
        response = httpx.get(
            FANDUEL_EVENT_URL,
            params={
                "_ak": FANDUEL_AK,
                "eventId": str(event_id),
                "tab": tab,
            },
            headers=HEADERS,
            timeout=20
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"Error fetching props for event {event_id} stat {stat_key}: {e}")
        return None

def build_game_id_map(fd_events):
    """
    Builds a lookup of {fanduel_event_id: nba_game_id}.
    Matches FanDuel event names against NBA schedule by team names.
    """
    todays_games = get_todays_games()
    game_id_map = {}

def build_game_id_map(fd_events):
    from datetime import date, timedelta
    from ingestion.nba_client import get_todays_games

    # FanDuel often shows tomorrow's games in the evening
    # so check both today and tomorrow
    todays_games = get_todays_games()
    tomorrows_games = get_todays_games(date.today() + timedelta(days=1))
    all_games = todays_games + tomorrows_games

    game_id_map = {}
    for game in all_games:
        home = game['home_team_name'].lower().split()[-1]
        away = game['away_team_name'].lower().split()[-1]
        for event in fd_events:
            event_name = event['name'].lower()
            if home in event_name and away in event_name:
                game_id_map[event['eventId']] = game['game_id']
                break

    return game_id_map

def parse_event_props(event_id, raw_data, stat_key, game_id_map, player_id_map):
    """
    Parses raw event-page JSON for one game and one stat type.
    Returns list of clean prop records.
    """
    if not raw_data:
        return []

    props = []
    captured_at = datetime.utcnow()
    markets = raw_data.get("attachments", {}).get("markets", {})

    for market in markets.values():
        if not isinstance(market, dict):
            continue

        market_name = market.get("marketName", "")
        parts = market_name.split(" - ", 1)
        if len(parts) != 2:
            continue

        player_name = parts[0].strip()
        stat_label = parts[1].strip()
        stat_type = STAT_TYPE_MAP.get(stat_label)
        if not stat_type:
            continue

        over_odds = None
        under_odds = None
        line = None

        for runner in market.get("runners") or []:
            result_type = (runner.get("result") or {}).get("type", "").upper()
            handicap = runner.get("handicap")
            american_odds = (
                runner.get("winRunnerOdds", {})
                .get("americanDisplayOdds", {})
                .get("americanOddsInt")
            )
            if handicap is not None:
                line = float(handicap)
            if result_type == "OVER":
                over_odds = american_odds
            elif result_type == "UNDER":
                under_odds = american_odds

        if not all([line, over_odds, under_odds]):
            continue

        # Map player name to NBA player ID
        player_id = player_id_map.get(player_name)
        if not player_id:
            for nba_name, pid in player_id_map.items():
                if player_name.lower() in nba_name.lower() or nba_name.lower() in player_name.lower():
                    player_id = pid
                    player_name = nba_name
                    break

        if not player_id:
            print(f"Could not map player: {player_name}")
            continue

        # Map event to NBA game ID using pre-built map
        nba_game_id = game_id_map.get(event_id, str(event_id))

        props.append({
            'game_id': nba_game_id,
            'player_id': player_id,
            'player_name': player_name,
            'stat_type': stat_type,
            'line': line,
            'over_odds': over_odds,
            'under_odds': under_odds,
            'captured_at': captured_at,
        })

    return props

def scrape_props():
    """
    Full scrape pipeline.
    Step 1 - get event IDs and names
    Step 2 - build game ID map against NBA schedule
    Step 3 - for each event, fetch each stat type
    Returns list of clean prop records ready for database write.
    """
    print("Building ID maps...")
    player_id_map = get_player_id_map()

    print("Fetching FanDuel event list...")
    fd_events = fetch_nba_events()
    if not fd_events:
        print("No NBA events found on FanDuel")
        return []

    game_id_map = build_game_id_map(fd_events)
    print(f"Mapped {len(game_id_map)} FanDuel events to NBA game IDs")

    all_props = []

    for event in fd_events:
        event_id = event['eventId']
        for stat_key in PROP_TABS:
            raw = fetch_event_props(event_id, stat_key)
            if raw:
                props = parse_event_props(
                    event_id, raw, stat_key, game_id_map, player_id_map
                )
                all_props.extend(props)
            time.sleep(0.5)

    print(f"Scraped {len(all_props)} props total")
    return all_props