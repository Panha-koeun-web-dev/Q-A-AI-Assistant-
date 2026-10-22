"""
src/database/__init__.py
-------------------------
Public API for the database package.

Import everything through this file so the rest of the app only needs:
    from src import db
    db.register_user(...)
    db.login_user(...)
    etc.
"""
from src.database.connection import (
    HAS_POSTGRES,
    PGDATABASE,
    get_connection,
    ensure_database_exists,
)
from src.database.schema import init_db
from src.database.auth import (
    hash_password,
    verify_password,
    register_user,
    login_user,
    get_user_by_token,
    logout_user,
)
from src.database.conversations import (
    get_user_conversations,
    create_conversation,
    get_conversation_messages,
    add_message,
    delete_conversation,
)
from src.database.memory import (
    get_user_memories,
    set_user_memory,
    clear_user_memories,
)

# Initialize tables on first import
try:
    init_db()
    if HAS_POSTGRES:
        print(f"[OK] PostgreSQL: Connected to '{PGDATABASE}' successfully.")
    else:
        print("[OK] Local Storage: SQLite initialized successfully.")
except Exception as _err:
    print(f"[Notice] DB initialization: {_err}")

