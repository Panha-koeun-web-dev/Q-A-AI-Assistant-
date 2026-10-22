"""
src/database/memory.py
-----------------------
User long-term memory — persists facts, preferences, and context
across conversations to personalize AI responses.
"""
from datetime import datetime

from src.database.connection import HAS_POSTGRES, get_connection


def get_user_memories(user_id: int) -> dict:
    """Returns all stored memories for a user as {key: value}."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM user_memories WHERE user_id = %s;", (user_id,))
                return {row[0]: row[1] for row in cur.fetchall()}
        else:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT key, value FROM user_memories WHERE user_id = ?;", (user_id,))
                return {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        return {}
    finally:
        conn.close()


def set_user_memory(user_id: int, key: str, value: str):
    """Inserts or updates a single memory key-value pair for a user."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_memories (user_id, key, value, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id, key) DO UPDATE
                        SET value = EXCLUDED.value, updated_at = NOW();
                    """,
                    (user_id, key.strip(), value.strip()),
                )
                conn.commit()
        else:
            with conn:
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    INSERT INTO user_memories (user_id, key, value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, key) DO UPDATE
                        SET value = excluded.value, updated_at = excluded.updated_at;
                    """,
                    (user_id, key.strip(), value.strip(), now),
                )
    finally:
        conn.close()


def clear_user_memories(user_id: int):
    """Deletes all stored memories for a user."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_memories WHERE user_id = %s;", (user_id,))
                conn.commit()
        else:
            with conn:
                conn.execute("DELETE FROM user_memories WHERE user_id = ?;", (user_id,))
    finally:
        conn.close()

