#!/usr/bin/env python3
"""Try to recover the corrupted database."""

import sqlite3
import shutil
from pathlib import Path

DB_PATH = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db")
SHM_PATH = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db-shm")
WAL_PATH = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db-wal")

# Backup the current state
backup_path = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db.backup")

print("Attempting database recovery...")
print(f"Original DB: {DB_PATH.stat().st_size / 1e6:.2f} MB")
print(f"WAL file: {WAL_PATH.stat().st_size / 1e6:.2f} MB")

# First, try to backup
try:
    shutil.copy2(DB_PATH, backup_path)
    print("✓ Backup created")
except Exception as e:
    print(f"✗ Backup failed: {e}")

# Try to recover by recreating without WAL mode
recovery_path = Path("/mnt/e/dev/projects/bettingbyte-v2/bettingbyte.db.recovery")

try:
    # Copy the main DB file
    shutil.copy2(DB_PATH, recovery_path)
    
    # Delete WAL and SHM files to force recovery
    if WAL_PATH.exists():
        WAL_PATH.unlink()
        print("✓ Removed WAL file")
    if SHM_PATH.exists():
        SHM_PATH.unlink()
        print("✓ Removed SHM file")
    
    # Try to open the recovered database
    conn = sqlite3.connect(str(recovery_path))
    cursor = conn.cursor()
    
    # Run integrity check
    cursor.execute("PRAGMA integrity_check;")
    integrity = cursor.fetchone()[0]
    print(f"\nIntegrity check result: {integrity}")
    
    if integrity == "ok":
        print("✓ Database recovered successfully!")
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables found: {len(tables)}")
        for table in tables[:10]:  # Show first 10
            print(f"  - {table[0]}")
        conn.close()
    else:
        print(f"✗ Database still corrupted: {integrity}")
        
except Exception as e:
    print(f"✗ Recovery failed: {e}")
    print("\nTrying alternative recovery...")
    
    # Try to read just the schema
    try:
        with open(recovery_path, 'rb') as f:
            header = f.read(100)
            print(f"File header (first 100 bytes): {header[:50]}")
    except Exception as e2:
        print(f"Cannot read file: {e2}")

print("\nRecovery attempt complete.")
