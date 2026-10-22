"""
src/database/connection.py
--------------------------
Database connection management — PostgreSQL with SQLite fallback.
"""
import os
import sqlite3

from dotenv import load_dotenv

load_dotenv(override=True)

PGHOST     = os.getenv("PGHOST", "localhost")
PGPORT     = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "q&a_ai_database")
PGUSER     = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")

# SQLite fallback path (relative to project root)
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "qa_ai.db")

# ---------------------------------------------------------------------------
# Try importing psycopg2 (PostgreSQL driver)
# ---------------------------------------------------------------------------
try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    print("[Notice] 'psycopg2' not found.")
    print("👉 To enable PostgreSQL, run: pip install psycopg2-binary")
    print("👉 Using embedded SQLite (qa_ai.db) as fallback.\n")


def ensure_database_exists():
    """Creates the PostgreSQL database if it does not exist yet."""
    if not HAS_POSTGRES or PGDATABASE.lower() == "postgres":
        return
    try:
        conn = psycopg2.connect(
            host=PGHOST, port=PGPORT, dbname="postgres",
            user=PGUSER, password=PGPASSWORD,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (PGDATABASE,))
            if not cur.fetchone():
                escaped = PGDATABASE.replace('"', '""')
                cur.execute(f'CREATE DATABASE "{escaped}";')
                print(f"[OK] PostgreSQL: Database '{PGDATABASE}' created.")
        conn.close()
    except Exception as e:
        print(f"[Notice] DB pre-check: {e}")


def get_connection():
    """Returns an active database connection (PostgreSQL or SQLite)."""
    if HAS_POSTGRES:
        return psycopg2.connect(
            host=PGHOST, port=PGPORT, dbname=PGDATABASE,
            user=PGUSER, password=PGPASSWORD,
        )
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

