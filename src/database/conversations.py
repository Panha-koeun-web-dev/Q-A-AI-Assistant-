"""
src/database/conversations.py
------------------------------
Conversation thread and message management.
"""
import secrets
from datetime import datetime

from psycopg2.extras import RealDictCursor

from src.database.connection import HAS_POSTGRES, get_connection


def get_user_conversations(user_id: int) -> list:
    """Returns all conversation threads for a user, newest first."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, title, created_at, updated_at "
                    "FROM conversations WHERE user_id = %s ORDER BY updated_at DESC;",
                    (user_id,),
                )
                rows = cur.fetchall()
                for r in rows:
                    if isinstance(r["created_at"], datetime):
                        r["created_at"] = r["created_at"].isoformat()
                    if isinstance(r["updated_at"], datetime):
                        r["updated_at"] = r["updated_at"].isoformat()
                return rows
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, title, created_at, updated_at "
                    "FROM conversations WHERE user_id = ? ORDER BY updated_at DESC;",
                    (user_id,),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def create_conversation(user_id: int, title: str = "New Chat") -> dict:
    """Creates a new conversation thread and returns it."""
    conv_id = secrets.token_hex(16)
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO conversations (id, user_id, title) VALUES (%s, %s, %s) "
                    "RETURNING id, title, created_at, updated_at;",
                    (conv_id, user_id, title),
                )
                conv = cur.fetchone()
                conn.commit()
                if isinstance(conv["created_at"], datetime):
                    conv["created_at"] = conv["created_at"].isoformat()
                if isinstance(conv["updated_at"], datetime):
                    conv["updated_at"] = conv["updated_at"].isoformat()
                return conv
        else:
            with conn:
                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?);",
                    (conv_id, user_id, title, now, now),
                )
                return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}
    finally:
        conn.close()


def get_conversation_messages(user_id: int, conversation_id: str) -> list:
    """Returns all messages in a conversation, in chronological order."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, role, content, created_at FROM messages "
                    "WHERE conversation_id = %s AND user_id = %s ORDER BY created_at ASC;",
                    (conversation_id, user_id),
                )
                rows = cur.fetchall()
                for r in rows:
                    if isinstance(r["created_at"], datetime):
                        r["created_at"] = r["created_at"].isoformat()
                return rows
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, role, content, created_at FROM messages "
                    "WHERE conversation_id = ? AND user_id = ? ORDER BY created_at ASC;",
                    (conversation_id, user_id),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def add_message(user_id: int, conversation_id: str, role: str, content: str):
    """Appends a message to a conversation and updates its title/timestamp."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title, (SELECT COUNT(*) FROM messages WHERE conversation_id = %s) AS msg_count "
                    "FROM conversations WHERE id = %s AND user_id = %s;",
                    (conversation_id, conversation_id, user_id),
                )
                conv = cur.fetchone()
                if not conv:
                    cur.execute(
                        "INSERT INTO conversations (id, user_id, title) VALUES (%s, %s, %s);",
                        (conversation_id, user_id, content[:40].strip() or "New Chat"),
                    )
                    msg_count = 0
                else:
                    msg_count = conv[1]

                cur.execute(
                    "INSERT INTO messages (conversation_id, user_id, role, content) VALUES (%s, %s, %s, %s);",
                    (conversation_id, user_id, role, content),
                )
                if role == "user" and msg_count == 0:
                    short_title = content.strip().split("\n")[0][:45]
                    cur.execute(
                        "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s;",
                        (short_title, conversation_id),
                    )
                else:
                    cur.execute("UPDATE conversations SET updated_at = NOW() WHERE id = %s;", (conversation_id,))
                conn.commit()
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT title, (SELECT COUNT(*) FROM messages WHERE conversation_id = ?) AS msg_count "
                    "FROM conversations WHERE id = ? AND user_id = ?;",
                    (conversation_id, conversation_id, user_id),
                )
                conv = cur.fetchone()
                if not conv:
                    cur.execute(
                        "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?);",
                        (conversation_id, user_id, content[:40].strip() or "New Chat"),
                    )
                    msg_count = 0
                else:
                    msg_count = conv[1]

                cur.execute(
                    "INSERT INTO messages (conversation_id, user_id, role, content) VALUES (?, ?, ?, ?);",
                    (conversation_id, user_id, role, content),
                )
                now = datetime.now().isoformat()
                if role == "user" and msg_count == 0:
                    short_title = content.strip().split("\n")[0][:45]
                    cur.execute(
                        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?;",
                        (short_title, now, conversation_id),
                    )
                else:
                    cur.execute("UPDATE conversations SET updated_at = ? WHERE id = ?;", (now, conversation_id))
    finally:
        conn.close()


def delete_conversation(user_id: int, conversation_id: str) -> bool:
    """Permanently deletes a conversation and all its messages."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s;", (conversation_id, user_id))
                conn.commit()
        else:
            with conn:
                conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?;", (conversation_id, user_id))
        return True
    except Exception:
        return False
    finally:
        conn.close()

