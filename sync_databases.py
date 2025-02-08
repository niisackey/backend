import os
import sys
import sqlite3
import pymysql
import traceback
from threading import Timer
from dotenv import load_dotenv
import threading
import atexit
from pathlib import Path

# Add the root directory to sys.path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
# Load environment variables
load_dotenv()


from db_utils import get_sqlite_connection, get_mysql_connection, SQLITE_DB_PATH

def sync_sqlite_to_mysql(entity_name, fields, update_fields):
    """Sync SQLite → MySQL"""
    sqlite_conn = get_sqlite_connection()
    print(f"🔍 Connected to SQLite DB: {SQLITE_DB_PATH}")
    
    if not sqlite_conn:
        print(f"❌ ERROR: Could not connect to SQLite database at {SQLITE_DB_PATH}")
        return
    
    mysql_conn = get_mysql_connection()
    if not mysql_conn:
        print(f"❌ Skipping {entity_name} sync, MySQL not available.")
        return

    try:
        sqlite_cursor = sqlite_conn.cursor()
        mysql_cursor = mysql_conn.cursor()

        # Debugging: Show the exact query
        query = f"SELECT {', '.join(fields)} FROM {entity_name} WHERE synced = 0"
        print(f"🔍 Executing query: {query}")
        
        sqlite_cursor.execute(query)
        rows = sqlite_cursor.fetchall()

        # Debugging: Print fetched rows
        print(f"🛠 Raw Data from SQLite for {entity_name}:")
        for row in rows:
            print(dict(row))  # Convert row to dictionary for readable output

        if not rows:
            print(f"✅ No unsynced records for {entity_name}.")
            return

        # Insert into MySQL
        for row in rows:
            values = tuple(row[field] for field in fields)  # Use fields dynamically
            insert_query = f"""
                INSERT INTO {entity_name} ({', '.join(fields)}) 
                VALUES ({', '.join(['%s'] * len(fields))})
                ON DUPLICATE KEY UPDATE {', '.join([f'{field}=VALUES({field})' for field in update_fields])}
            """

            try:
                print(f"📥 SQL Query:\n{insert_query}")
                print(f"📥 Values: {values}")
                mysql_cursor.execute(insert_query, values)
                mysql_conn.commit()
                
                if mysql_cursor.rowcount == 0:
                    print(f"⚠️ Warning: No rows were affected in MySQL for {entity_name} ID {row['id']}")

                # Only update `synced = 1` after successful MySQL insert
                sqlite_cursor.execute(f"UPDATE {entity_name} SET synced = 1 WHERE id = ?", (row["id"],))
                sqlite_conn.commit()
                print(f"✅ Successfully synced {entity_name} ID {row['id']} to MySQL.")

            except pymysql.MySQLError as e:
                print(f"❌ MySQL Insert Error for {entity_name}, ID {row['id']}: {e}")
                mysql_conn.rollback()

    finally:
        sqlite_conn.close()
        mysql_conn.close()
        
sync_timer = None

def auto_sync():
    """Automatically syncs SQLite → MySQL every 2 minutes."""
    global sync_timer
    print("Running auto-sync...")

    sync_sqlite_to_mysql("sales", ["id", "total_amount", "payment_method", "date", "synced"], ["total_amount", "payment_method", "date"])
    sync_sqlite_to_mysql("inventory", ["id", "name", "quantity", "price", "barcode", "category", "synced"], ["name", "quantity", "price", "barcode", "category"])
    sync_sqlite_to_mysql("users", ["id", "username", "password", "role_id", "synced"], ["username", "password", "role_id"])
    sync_sqlite_to_mysql("roles", ["id", "role_name", "permissions", "synced"], ["role_name", "permissions"])

    print("Auto-sync completed!")

    # Schedule next sync in 2 minutes
    sync_timer = threading.Timer(120, auto_sync)  # 120 seconds = 2 minutes
    sync_timer.start()

# Ensure timer is stopped when script exits
def stop_sync():
    global sync_timer
    if sync_timer:
        sync_timer.cancel()
        print("🛑 Sync timer stopped.")

atexit.register(stop_sync)

if __name__ == "__main__":
    auto_sync()
