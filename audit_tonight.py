#!/usr/bin/env python3
"""Data quality audit for tonight's NBA slate."""

import sqlite3
from pathlib import Path

DB_PATH = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db")
TODAY = "2026-03-17"

def run_audit():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("=" * 60)
    print(f"TONIGHT'S NBA SLATE AUDIT - {TODAY}")
    print("=" * 60)
    print()
    
    # 1. Games scheduled for today
    print("1. GAMES SCHEDULED TODAY")
    print("-" * 40)
    cursor.execute("""
        SELECT COUNT(*) as total,
               MIN(home_team) as first_home,
               MIN(away_team) as first_away
        FROM games WHERE game_date = ?
    """, (TODAY,))
    row = cursor.fetchone()
    print(f"   Total games: {row[0]}")
    if row[0] > 0:
        print(f"   First game: {row[1]} @ {row[2]}")
    
    cursor.execute("""
        SELECT game_id, home_team, away_team, game_time
        FROM games WHERE game_date = ? ORDER BY game_time
    """, (TODAY,))
    games = cursor.fetchall()
    for g in games:
        print(f"   - {g[2]} @ {g[1]} at {g[3]}")
    print()
    
    # 2. Player props per game
    print("2. PLAYER PROPS BY GAME")
    print("-" * 40)
    cursor.execute("""
        SELECT g.game_id, g.home_team, g.away_team, COUNT(DISTINCT p.prop_id) as prop_count
        FROM games g
        LEFT JOIN player_props p ON g.game_id = p.game_id
        WHERE g.game_date = ?
        GROUP BY g.game_id, g.home_team, g.away_team
        ORDER BY prop_count ASC
    """, (TODAY,))
    props = cursor.fetchall()
    for p in props:
        status = "ALERT: ZERO PROPS" if p[3] == 0 else f"OK: {p[3]} props"
        print(f"   {status} - {p[1]} @ {p[2]}")
    print()
    
    # 3. Rotations by game
    print("3. ROTATIONS BY GAME")
    print("-" * 40)
    cursor.execute("""
        SELECT g.game_id, g.home_team, g.away_team, COUNT(DISTINCT r.player_id) as players
        FROM games g
        LEFT JOIN rotations r ON g.game_id = r.game_id AND r.status = 'STARTER'
        WHERE g.game_date = ?
        GROUP BY g.game_id, g.home_team, g.away_team
        ORDER BY players ASC
    """, (TODAY,))
    rotations = cursor.fetchall()
    for r in rotations:
        status = "ALERT: NO ROTATIONS" if r[3] == 0 else f"OK: {r[3]} starters"
        print(f"   {status} - {r[1]} @ {r[2]}")
    print()
    
    # 4. Today's injury report
    print("4. INJURY REPORT STATUS")
    print("-" * 40)
    cursor.execute("""
        SELECT DISTINCT game_date
        FROM injury_snapshots
        WHERE game_date = ?
    """, (TODAY,))
    snapshot = cursor.fetchone()
    if snapshot:
        print(f"   Injury snapshot exists for {TODAY}")
        cursor.execute("""
            SELECT player_name, status, game_date
            FROM injuries i
            JOIN injury_snapshots s ON i.snapshot_id = s.snapshot_id
            WHERE s.game_date = ? AND i.status IN ('QUESTIONABLE', 'DOUBTFUL', 'OUT')
            ORDER BY status
        """, (TODAY,))
        injuries = cursor.fetchall()
        if injuries:
            print(f"   Players affected ({len(injuries)}):")
            for i in injuries:
                print(f"   - {i[0]}: {i[1]}")
        else:
            print("   No players marked Q/D/OUT today")
    else:
        print(f"   ALERT: NO INJURY SNAPSHOT FOR {TODAY}")
    print()
    
    # 5. Summary
    print("5. AUDIT SUMMARY")
    print("-" * 40)
    cursor.execute("SELECT COUNT(*) FROM games WHERE game_date = ?", (TODAY,))
    total_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games g LEFT JOIN player_props p ON g.game_id = p.game_id WHERE g.game_date = ? AND p.prop_id IS NULL", (TODAY,))
    games_no_props = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM games g LEFT JOIN rotations r ON g.game_id = r.game_id WHERE g.game_date = ? AND r.player_id IS NULL", (TODAY,))
    games_no_rotations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM injury_snapshots WHERE game_date = ?", (TODAY,))
    has_injury_snapshot = cursor.fetchone()[0] > 0
    
    print(f"   Games with props: {total_games - games_no_props}/{total_games}")
    print(f"   Games with rotations: {total_games - games_no_rotations}/{total_games}")
    print(f"   Injury snapshot: {'Yes' if has_injury_snapshot else 'No'}")
    
    print()
    print("=" * 60)
    
    conn.close()

if __name__ == "__main__":
    run_audit()
