"""
src/database/conversations.py
------------------------------
Conversation thread and message management.
Supports psycopg v3, psycopg2, and SQLite.
"""
import json
import secrets
from datetime import datetime

from src.database.connection import HAS_POSTGRES, get_connection, fetchdict


def _ts(value) -> str:
    """Convert datetime to ISO string if needed."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_attachments(raw_att):
    """Safely deserialize attachments JSON from DB row."""
    if not raw_att:
        return []
    if isinstance(raw_att, list):
        return raw_att
    try:
        return json.loads(raw_att)
    except Exception:
        return []


def get_user_conversations(user_id: int) -> list:
    """Returns all conversation threads for a user, newest first."""
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, created_at, updated_at "
                    "FROM conversations WHERE user_id = %s ORDER BY updated_at DESC;",
                    (user_id,),
                )
                rows = [fetchdict(r) for r in cur.fetchall()]
                for r in rows:
                    r["created_at"] = _ts(r.get("created_at"))
                    r["updated_at"] = _ts(r.get("updated_at"))
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
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (id, user_id, title) VALUES (%s, %s, %s) "
                    "RETURNING id, title, created_at, updated_at;",
                    (conv_id, user_id, title),
                )
                conv = fetchdict(cur.fetchone())
                conn.commit()
                conv["created_at"] = _ts(conv.get("created_at"))
                conv["updated_at"] = _ts(conv.get("updated_at"))
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
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, role, content, attachments, created_at FROM messages "
                    "WHERE conversation_id = %s AND user_id = %s ORDER BY created_at ASC;",
                    (conversation_id, user_id),
                )
                rows = [fetchdict(r) for r in cur.fetchall()]
                for r in rows:
                    r["created_at"] = _ts(r.get("created_at"))
                    r["attachments"] = _parse_attachments(r.get("attachments"))
                return rows
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, role, content, attachments, created_at FROM messages "
                    "WHERE conversation_id = ? AND user_id = ? ORDER BY created_at ASC;",
                    (conversation_id, user_id),
                )
                rows = [dict(r) for r in cur.fetchall()]
                for r in rows:
                    r["attachments"] = _parse_attachments(r.get("attachments"))
                return rows
    except Exception:
        return []
    finally:
        conn.close()


def add_message(user_id: int, conversation_id: str, role: str, content: str, attachments: list = None):
    """Appends a message to a conversation and updates its title/timestamp."""
    conn = get_connection()
    att_json = json.dumps(attachments) if attachments else None
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
                    row = fetchdict(conv)
                    msg_count = row["msg_count"]

                cur.execute(
                    "INSERT INTO messages (conversation_id, user_id, role, content, attachments) "
                    "VALUES (%s, %s, %s, %s, %s);",
                    (conversation_id, user_id, role, content, att_json),
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
                    msg_count = conv["msg_count"]

                cur.execute(
                    "INSERT INTO messages (conversation_id, user_id, role, content, attachments) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (conversation_id, user_id, role, content, att_json),
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


def update_conversation_title(conversation_id: str, title: str) -> bool:
    """Updates the conversation title in the database."""
    title = (title or "").strip()[:80]
    if not title:
        return False
    conn = get_connection()
    try:
        if HAS_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s;",
                    (title, conversation_id),
                )
                conn.commit()
        else:
            with conn:
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?;",
                    (title, now, conversation_id),
                )
        return True
    except Exception:
        return False
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
