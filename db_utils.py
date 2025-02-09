import os
import sys
import sqlite3
import pymysql
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# -------------------- PATH CONFIGURATION --------------------
def get_base_path():
    """Get the correct base path for both development and packaged environments"""
    try:
        # When frozen (executable) or in production
        return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
    except Exception as e:
        print(f"⚠️ Path resolution error: {str(e)}")
        return Path.cwd()

BASE_DIR = Path(__file__).parent
SQLITE_DB_PATH = BASE_DIR / "database.db"
SSL_CA_PATH = BASE_DIR / "ssl" / "ca.pem"  # Aiven SSL cert path

# -------------------- DATABASE CONFIGURATION --------------------
def get_mysql_config():
    """Get MySQL configuration with proper SSL handling"""
    return {
        'host': os.getenv("AIVEN_HOST", "localhost"),
        'port': int(os.getenv("AIVEN_PORT", "3306")),
        'user': os.getenv("AIVEN_USER", "root"),
        'password': os.getenv("AIVEN_PASSWORD", ""),
        'database': os.getenv("AIVEN_DB", "defaultdb"),
        'ssl': {
            'ca': SSL_CA_PATH.read_text() if SSL_CA_PATH.exists() else None
        }
    }

# -------------------- CONNECTION HANDLERS --------------------
def get_sqlite_connection():
    """Get SQLite connection with error handling"""
    try:
        conn = sqlite3.connect(str(SQLITE_DB_PATH))
        conn.row_factory = sqlite3.Row
        print(f"✅ Connected to SQLite at {SQLITE_DB_PATH}")
        return conn
    except sqlite3.Error as e:
        print(f"❌ SQLite Connection Error: {str(e)}")
        return None

def get_mysql_connection():
    """Connect to MySQL **without SSL verification**"""
    try:
        conn = pymysql.connect(
            host=os.getenv("AIVEN_HOST", "localhost"),
            port=int(os.getenv("AIVEN_PORT", "3306")),
            user=os.getenv("AIVEN_USER", "root"),
            password=os.getenv("AIVEN_PASSWORD", ""),
            database=os.getenv("AIVEN_DB", "defaultdb"),
            ssl={'ssl': {'ca': None}},  # Disable SSL verification
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"✅ Connected to MySQL at {os.getenv('AIVEN_HOST')}")
        return conn
    except pymysql.MySQLError as e:
        print(f"❌ MySQL Connection Error: {str(e)}")
        return None

# -------------------- MAIN DATABASE SWITCHER --------------------
def get_database_connection(use_cloud=None):
    """Smart database connection selector"""
    if use_cloud is None:
        use_cloud = os.getenv("USE_CLOUD_DB", "false").lower() == "true"
        
    return get_mysql_connection() if use_cloud else get_sqlite_connection()

# -------------------- DEBUGGING & VALIDATION --------------------
if __name__ == "__main__":
    print("\n🔍 Database Configuration Validation:")
    print(f"Base Directory: {BASE_DIR}")
    print(f"SQLite Path: {SQLITE_DB_PATH} ({'Exists' if SQLITE_DB_PATH.exists() else 'Missing'})")
    print(f"SSL CA Path: {SSL_CA_PATH} ({'Exists' if SSL_CA_PATH.exists() else 'Missing'})")
    
    print("\n🔧 Testing Connections:")
    sqlite_conn = get_sqlite_connection()
    mysql_conn = get_mysql_connection()
    
    if sqlite_conn:
        sqlite_conn.close()
    if mysql_conn:
        mysql_conn.close()