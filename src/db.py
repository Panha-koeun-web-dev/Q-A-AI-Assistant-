"""
src/db.py
---------
Backward-compatibility shim.
All database logic now lives in src/database/*.py

This file re-exports everything so existing imports like:
    from src import db
    db.register_user(...)
...continue to work without any changes.
"""
from src.database import (  # noqa: F401 — re-export all public symbols
    HAS_POSTGRES,
    PGDATABASE,
    get_connection,
    ensure_database_exists,
    init_db,
    hash_password,
    verify_password,
    register_user,
    login_user,
    get_user_by_token,
    logout_user,
    get_user_conversations,
    create_conversation,
    get_conversation_messages,
    add_message,
    delete_conversation,
    update_conversation_title,
    get_user_memories,
    set_user_memory,
    clear_user_memories,
)
