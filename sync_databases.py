import os
import sys
import sqlite3
import pymysql
import threading
import traceback
import atexit
from dotenv import load_dotenv
from pathlib import Path

# ✅ Deployment environment detection
if os.getenv('RENDER'):
    ROOT_DIR = Path("/opt/render/project/src")
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT_DIR))

try:
    from db_utils import (
        get_mysql_connection, 
        get_sqlite_connection,
        SQLITE_DB_PATH  # Added missing import
    )
    print("✅ Successfully imported `db_utils.py`!")
except (ModuleNotFoundError, ImportError) as e:
    print(f"❌ ERROR: Could not import dependencies: {e}")
    sys.exit(1)

load_dotenv()

# ✅ Table validation
VALID_TABLES = {"sales", "inventory", "users", "roles"}

# -------------------- SYNC FUNCTION --------------------
def sync_sqlite_to_mysql(entity_name, fields, update_fields):
    """Sync SQLite → MySQL."""
    sqlite_conn = get_sqlite_connection()
    mysql_conn = get_mysql_connection()

    if not sqlite_conn:
        print(f"❌ ERROR: Could not connect to SQLite database at {SQLITE_DB_PATH}")
        return
    if not mysql_conn:
        print(f"❌ ERROR: MySQL connection failed. Skipping sync for `{entity_name}`.")
        return

    try:
        sqlite_cursor = sqlite_conn.cursor()
        mysql_cursor = mysql_conn.cursor()

        # ✅ Fetch unsynced records from SQLite
        query = f"SELECT {', '.join(fields)} FROM {entity_name} WHERE synced = 0"
        sqlite_cursor.execute(query)
        rows = sqlite_cursor.fetchall()

        if not rows:
            print(f"✅ No unsynced records for `{entity_name}`.")
            return

        # ✅ Insert into MySQL
        for row in rows:
            try:
                values = tuple(row[field] for field in fields)  # Use fields dynamically
                insert_query = f"""
                    INSERT INTO {entity_name} ({', '.join(fields)}) 
                    VALUES ({', '.join(['%s'] * len(fields))})
                    ON DUPLICATE KEY UPDATE {', '.join([f'{field}=VALUES({field})' for field in update_fields])}
                """

                mysql_cursor.execute(insert_query, values)
                mysql_conn.commit()

                # ✅ Mark as synced in SQLite
                sqlite_cursor.execute(f"UPDATE {entity_name} SET synced = 1 WHERE id = ?", (row["id"],))
                sqlite_conn.commit()

                print(f"✅ Synced `{entity_name}` ID `{row['id']}` to MySQL.")

            except pymysql.MySQLError as e:
                print(f"❌ MySQL Insert Error for `{entity_name}`, ID `{row['id']}`: {e}")
                mysql_conn.rollback()

    except Exception:
        print(f"❌ Sync Error for `{entity_name}`: {traceback.format_exc()}")

    finally:
        sqlite_conn.close()
        mysql_conn.close()

# -------------------- AUTO-SYNC FUNCTION --------------------
sync_timer = None

def auto_sync():
    """Automatically syncs SQLite → MySQL every 2 minutes."""
    global sync_timer
    print("🔄 Running auto-sync...")

    try:
        sync_sqlite_to_mysql("sales", ["id", "total_amount", "payment_method", "date", "synced"], ["total_amount", "payment_method", "date"])
        sync_sqlite_to_mysql("inventory", ["id", "name", "quantity", "price", "barcode", "category", "synced"], ["name", "quantity", "price", "barcode", "category"])
        sync_sqlite_to_mysql("users", ["id", "username", "password", "role_id", "synced"], ["username", "password", "role_id"])
        sync_sqlite_to_mysql("roles", ["id", "role_name", "permissions", "synced"], ["role_name", "permissions"])
        
        print("✅ Auto-sync completed successfully!")

    except Exception:
        print(f"❌ Auto-sync failed: {traceback.format_exc()}")

    # ✅ Schedule next sync in 2 minutes
    sync_timer = threading.Timer(120, auto_sync)
    sync_timer.start()

# -------------------- SHUTDOWN HANDLER --------------------
def stop_sync():
    """Stops the auto-sync timer when the script exits."""
    global sync_timer
    if sync_timer:
        sync_timer.cancel()
        print("🛑 Sync timer stopped.")

atexit.register(stop_sync)

# -------------------- START SYNC --------------------
if __name__ == "__main__":
    auto_sync()
