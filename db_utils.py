import os
import sys
import sqlite3
import pymysql
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read database mode from .env
USE_CLOUD_DB = os.getenv("USE_CLOUD_DB", "False").lower() == "true"

# MySQL Configuration (Local or Cloud)
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "pos_system")
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "")

# ✅ Define database path for local & deployed environments
if getattr(sys, 'frozen', False):  # Running as an executable
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Use script directory

SQLITE_DB_PATH = os.path.join(BASE_DIR, "database.db")  # Set path to SQLite DB

# Debugging: Confirm database path
print(f"🔍 Using SQLite DB Path: {SQLITE_DB_PATH}")
if not os.path.exists(SQLITE_DB_PATH):
    print(f"❌ ERROR: SQLite database NOT FOUND at {SQLITE_DB_PATH}")
else:
    print(f"✅ SQLite database FOUND at {SQLITE_DB_PATH}")

def get_database_path():
    """Returns the absolute path to the SQLite database file."""
    return SQLITE_DB_PATH

def get_sqlite_connection():
    """Returns a SQLite connection to the database."""
    try:
        if not os.path.exists(SQLITE_DB_PATH):
            print(f"❌ ERROR: SQLite database not found at {SQLITE_DB_PATH}")
            return None

        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ SQLite Connection Error: {e}")
        return None

def get_mysql_connection():
    """Returns a MySQL connection."""
    try:
        ssl_options = {"ca": CA_CERT_PATH} if CA_CERT_PATH else None
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_options if USE_CLOUD_DB else None
        )
        return conn
    except pymysql.MySQLError as e:
        print(f"❌ MySQL Connection Error: {e}")
        return None

def get_database_connection():
    """Returns appropriate database connection (MySQL or SQLite)."""
    return get_mysql_connection() if USE_CLOUD_DB else get_sqlite_connection()
