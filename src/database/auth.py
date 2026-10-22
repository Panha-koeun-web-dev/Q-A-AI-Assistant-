"""
src/database/auth.py
---------------------
User registration, login, session management, and password hashing.
"""
import hashlib
import secrets

from psycopg2.extras import RealDictCursor

from src.database.connection import HAS_POSTGRES, get_connection


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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username,))
                if cur.fetchone():
                    return {"success": False, "error": "Username already exists. Please choose another."}
                cur.execute(
                    "INSERT INTO users (username, email, password_hash, password_salt) "
                    "VALUES (%s, %s, %s, %s) RETURNING id, username, email;",
                    (username, email or None, pwd_hash, salt_hex),
                )
                user = cur.fetchone()
                token = secrets.token_hex(32)
                cur.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) "
                    "VALUES (%s, %s, NOW() + INTERVAL '30 days');",
                    (token, user["id"]),
                )
                conn.commit()
                return {"success": True, "token": token,
                        "user": {"id": user["id"], "username": user["username"], "email": user["email"]}}
        else:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?);", (username,))
                if cur.fetchone():
                    return {"success": False, "error": "Username already exists. Please choose another."}
                cur.execute(
                    "INSERT INTO users (username, email, password_hash, password_salt) VALUES (?, ?, ?, ?);",
                    (username, email or None, pwd_hash, salt_hex),
                )
                user_id = cur.lastrowid
                token = secrets.token_hex(32)
                conn.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) "
                    "VALUES (?, ?, datetime('now', '+30 days'));",
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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, username, email, password_hash, password_salt "
                    "FROM users WHERE LOWER(username) = LOWER(%s);",
                    (username,),
                )
                user = cur.fetchone()
                if not user or not verify_password(password, user["password_hash"], user["password_salt"]):
                    return {"success": False, "error": "Invalid username or password."}
                token = secrets.token_hex(32)
                cur.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) "
                    "VALUES (%s, %s, NOW() + INTERVAL '30 days');",
                    (token, user["id"]),
                )
                conn.commit()
                return {"success": True, "token": token,
                        "user": {"id": user["id"], "username": user["username"], "email": user["email"]}}
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, email, password_hash, password_salt "
                    "FROM users WHERE LOWER(username) = LOWER(?);",
                    (username,),
                )
                row = cur.fetchone()
                if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
                    return {"success": False, "error": "Invalid username or password."}
                token = secrets.token_hex(32)
                conn.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) "
                    "VALUES (?, ?, datetime('now', '+30 days'));",
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
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT u.id, u.username, u.email FROM sessions s "
                    "JOIN users u ON s.user_id = u.id "
                    "WHERE s.token = %s AND s.expires_at > NOW();",
                    (token,),
                )
                return cur.fetchone()
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

