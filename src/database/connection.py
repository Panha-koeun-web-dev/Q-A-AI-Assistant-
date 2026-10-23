
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

PGHOST     = os.getenv("PGHOST", "localhost")
PGPORT     = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "q&a_ai_database")
PGUSER     = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")

SQLITE_PATH = str(Path(__file__).resolve().parent.parent.parent / "qa_ai.db")

# ---------------------------------------------------------------------------
# Detect which PostgreSQL driver is available
# ---------------------------------------------------------------------------
HAS_POSTGRES = False
_PG_DRIVER = None   # "psycopg3" | "psycopg2" | None

try:
    import psycopg                          # psycopg v3
    from psycopg.rows import dict_row as _pg3_dict_row
    HAS_POSTGRES = True
    _PG_DRIVER = "psycopg3"
except ImportError:
    pass

if not HAS_POSTGRES:
    try:
        import psycopg2                     # psycopg v2
        from psycopg2.extras import RealDictCursor as _pg2_RealDictCursor
        HAS_POSTGRES = True
        _PG_DRIVER = "psycopg2"
    except (ImportError, Exception):
        pass

if not HAS_POSTGRES:
    print("[Notice] No PostgreSQL driver found (tried psycopg v3 and psycopg2).")
    print("👉 Run:  pip install \"psycopg[binary]\"")
    print("👉 Using SQLite fallback (qa_ai.db).\n")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_psycopg3() -> bool:
    return _PG_DRIVER == "psycopg3"

def is_psycopg2() -> bool:
    return _PG_DRIVER == "psycopg2"


def ensure_database_exists():
    """Creates the PostgreSQL database if it does not already exist."""
    if not HAS_POSTGRES or PGDATABASE.lower() == "postgres":
        return
    try:
        if is_psycopg3():
            import psycopg
            with psycopg.connect(
                host=PGHOST, port=PGPORT, dbname="postgres",
                user=PGUSER, password=PGPASSWORD,
                autocommit=True,
            ) as conn:
                cur = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (PGDATABASE,)
                )
                if not cur.fetchone():
                    escaped = PGDATABASE.replace('"', '""')
                    conn.execute(f'CREATE DATABASE "{escaped}"')
                    print(f"[OK] PostgreSQL: Database '{PGDATABASE}' created.")
        else:
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            conn = psycopg2.connect(
                host=PGHOST, port=PGPORT, dbname="postgres",
                user=PGUSER, password=PGPASSWORD,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PGDATABASE,))
                if not cur.fetchone():
                    escaped = PGDATABASE.replace('"', '""')
                    cur.execute(f'CREATE DATABASE "{escaped}"')
                    print(f"[OK] PostgreSQL: Database '{PGDATABASE}' created.")
            conn.close()
    except Exception as e:
        print(f"[Notice] DB pre-check: {e}")


def get_connection():
    """Returns an active database connection (PostgreSQL or SQLite fallback)."""
    if HAS_POSTGRES:
        if is_psycopg3():
            import psycopg
            return psycopg.connect(
                host=PGHOST, port=PGPORT, dbname=PGDATABASE,
                user=PGUSER, password=PGPASSWORD,
                row_factory=_pg3_dict_row,
            )
        else:
            import psycopg2
            return psycopg2.connect(
                host=PGHOST, port=PGPORT, dbname=PGDATABASE,
                user=PGUSER, password=PGPASSWORD,
            )
    # SQLite fallback
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def fetchdict(cursor_or_row):
    """Normalises a DB row to a plain dict regardless of driver."""
    if cursor_or_row is None:
        return None
    if isinstance(cursor_or_row, dict):
        return cursor_or_row
    return dict(cursor_or_row)
