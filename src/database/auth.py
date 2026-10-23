"""
src/database/auth.py
---------------------
User registration, login, session management, and password hashing.
Supports psycopg v3, psycopg2, and SQLite.
"""
import hashlib
import secrets

from src.database.connection import HAS_POSTGRES, get_connection, is_psycopg3, fetchdict


# ---------------------------------------------------------------------------
# Password Utilities
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """Generates a secure PBKDF2-SHA256 hash with salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hashed.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, stored_salt_hex: str) -> bool:
    """Verifies a plaintext password against its stored hash and salt."""
    salt = bytes.fromhex(stored_salt_hex)
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()
    return secrets.compare_digest(computed, stored_hash)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cursor(conn):
    """Returns a dict-returning cursor appropriate for the active driver."""
    if is_psycopg3():
        return conn.cursor()      # already uses dict_row from connection factory
    if HAS_POSTGRES:
        from psycopg2.extras import RealDictCursor
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()          # SQLite with Row factory


def _pg_param(driver_is_pg3: bool) -> str:
    """Returns %s (psycopg) or ? (SQLite)."""
    return "%s" if HAS_POSTGRES else "?"


def _p(n: int = 1) -> str:
    """Shorthand: returns the right placeholder for current driver."""
    return "%s" if HAS_POSTGRES else "?"


# ---------------------------------------------------------------------------
# Registration & Login
# ---------------------------------------------------------------------------

def register_user(username: str, password: str, email: str = None) -> dict:
    """Creates a new user account and returns a session token."""
    username = username.strip()
    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if len(password) < 4:
        return {"success": False, "error": "Password must be at least 4 characters."}

    pwd_hash, salt_hex = hash_password(password)
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            p = "%s"
            with conn.cursor() as cur:
                cur.execute(f"SELECT id FROM users WHERE LOWER(username) = LOWER({p});", (username,))
                if fetchdict(cur.fetchone()):
                    return {"success": False, "error": "Username already exists. Please choose another."}
                cur.execute(
                    f"INSERT INTO users (username, email, password_hash, password_salt) "
                    f"VALUES ({p},{p},{p},{p}) RETURNING id, username, email;",
                    (username, email or None, pwd_hash, salt_hex),
                )
                user = fetchdict(cur.fetchone())
                token = secrets.token_hex(32)
                if is_psycopg3():
                    cur.execute(
                        f"INSERT INTO sessions (token, user_id, expires_at) "
                        f"VALUES ({p},{p}, NOW() + INTERVAL '30 days');",
                        (token, user["id"]),
                    )
                    conn.commit()
                else:
                    cur.execute(
                        f"INSERT INTO sessions (token, user_id, expires_at) "
                        f"VALUES ({p},{p}, NOW() + INTERVAL '30 days');",
                        (token, user["id"]),
                    )
                    conn.commit()
                return {"success": True, "token": token,
                        "user": {"id": user["id"], "username": user["username"], "email": user["email"]}}
        else:
            p = "?"
            with conn:
                cur = conn.cursor()
                cur.execute(f"SELECT id FROM users WHERE LOWER(username) = LOWER({p});", (username,))
                if cur.fetchone():
                    return {"success": False, "error": "Username already exists. Please choose another."}
                cur.execute(
                    f"INSERT INTO users (username, email, password_hash, password_salt) VALUES ({p},{p},{p},{p});",
                    (username, email or None, pwd_hash, salt_hex),
                )
                user_id = cur.lastrowid
                token = secrets.token_hex(32)
                conn.execute(
                    f"INSERT INTO sessions (token, user_id, expires_at) VALUES ({p},{p}, datetime('now', '+30 days'));",
                    (token, user_id),
                )
                return {"success": True, "token": token,
                        "user": {"id": user_id, "username": username, "email": email or None}}
    except Exception as e:
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    """Authenticates a user and returns a new session token."""
    username = username.strip()
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            p = "%s"
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, username, email, password_hash, password_salt "
                    f"FROM users WHERE LOWER(username) = LOWER({p});",
                    (username,),
                )
                user = fetchdict(cur.fetchone())
                if not user or not verify_password(password, user["password_hash"], user["password_salt"]):
                    return {"success": False, "error": "Invalid username or password."}
                token = secrets.token_hex(32)
                cur.execute(
                    f"INSERT INTO sessions (token, user_id, expires_at) "
                    f"VALUES ({p},{p}, NOW() + INTERVAL '30 days');",
                    (token, user["id"]),
                )
                conn.commit()
                return {"success": True, "token": token,
                        "user": {"id": user["id"], "username": user["username"], "email": user["email"]}}
        else:
            p = "?"
            with conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT id, username, email, password_hash, password_salt "
                    f"FROM users WHERE LOWER(username) = LOWER({p});",
                    (username,),
                )
                row = cur.fetchone()
                if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
                    return {"success": False, "error": "Invalid username or password."}
                token = secrets.token_hex(32)
                conn.execute(
                    f"INSERT INTO sessions (token, user_id, expires_at) VALUES ({p},{p}, datetime('now', '+30 days'));",
                    (token, row["id"]),
                )
                return {"success": True, "token": token,
                        "user": {"id": row["id"], "username": row["username"], "email": row["email"]}}
    except Exception as e:
        return {"success": False, "error": f"Login failed: {str(e)}"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

def get_user_by_token(token: str) -> dict | None:
    """Returns the user associated with a valid session token, or None."""
    if not token:
        return None
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            p = "%s"
            expires_check = "NOW()" if True else "datetime('now')"
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT u.id, u.username, u.email FROM sessions s "
                    f"JOIN users u ON s.user_id = u.id "
                    f"WHERE s.token = {p} AND s.expires_at > NOW();",
                    (token,),
                )
                return fetchdict(cur.fetchone())
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT u.id, u.username, u.email FROM sessions s "
                    "JOIN users u ON s.user_id = u.id "
                    "WHERE s.token = ? AND s.expires_at > datetime('now');",
                    (token,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def logout_user(token: str) -> bool:
    """Deletes the session token (logs the user out)."""
    if not token:
        return True
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token = %s;", (token,))
                conn.commit()
        else:
            with conn:
                conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
        return True
    except Exception:
        return False
    finally:
        conn.close()
