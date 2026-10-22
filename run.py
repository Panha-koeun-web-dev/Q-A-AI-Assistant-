"""
run.py — Q&A AI Assistant Web Server
Entry point for the browser-based Q&A AI application.

Usage:
    python run.py

Opens http://127.0.0.1:5000 automatically in your default browser.
"""

import json
import os
import socket
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from src import db
from src.ai_service import query_openai

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(override=True)
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b").strip()
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not API_KEY or API_KEY.startswith("your_"):
    raise SystemExit(
        "Error: OPENAI_API_KEY is missing or invalid in your .env file.\n"
        "To get a 100% free key, visit: https://console.groq.com/keys"
    )

# ---------------------------------------------------------------------------
# MIME type helper
# ---------------------------------------------------------------------------

_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def _mime_for(path: Path) -> str:
    return _MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


# ---------------------------------------------------------------------------
# Request Handler
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):

    def _send_response(self, content_type: str, body_bytes: bytes, status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, data: dict, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self._send_response("application/json", body, status)

    def _send_file(self, file_path: Path):
        """Read a file from disk and send it with the appropriate MIME type."""
        if file_path.exists() and file_path.is_file():
            body = file_path.read_bytes()
            self._send_response(_mime_for(file_path), body)
        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _get_auth_user(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1].strip()
            return db.get_user_by_token(token)
        return None

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Main SPA page
        if path in ("/", "/index.html"):
            self._send_file(TEMPLATES_DIR / "index.html")

        # Logo (check both static/images/ and root)
        elif path in ("/logo.jpg", "/favicon.ico"):
            logo = STATIC_DIR / "images" / "logo.jpg"
            if not logo.exists():
                logo = BASE_DIR / "logo.jpg"
            self._send_file(logo)

        # Static assets — /static/css/*, /static/js/*, /static/images/*
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]          # e.g. "css/style.css"
            self._send_file(STATIC_DIR / rel)

        # Auth — current user
        elif path == "/api/auth/me":
            user = self._get_auth_user()
            if user:
                self._send_json({"success": True, "user": user})
            else:
                self._send_json({"success": False, "error": "Not authenticated"})

        # Conversations list
        elif path == "/api/conversations":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            convs = db.get_user_conversations(user["id"])
            self._send_json({"success": True, "conversations": convs})

        # Single conversation messages
        elif path.startswith("/api/conversations/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            conv_id = path.split("/api/conversations/")[1]
            messages = db.get_conversation_messages(user["id"], conv_id)
            self._send_json({"success": True, "messages": messages})

        # Memories
        elif path == "/api/memories":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            memories = db.get_user_memories(user["id"])
            self._send_json({"success": True, "memories": memories})

        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    # ------------------------------------------------------------------
    # POST routes
    # ------------------------------------------------------------------

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception:
            payload = {}

        if path == "/api/auth/register":
            username = payload.get("username", "")
            password = payload.get("password", "")
            email = payload.get("email", "")
            result = db.register_user(username, password, email)
            self._send_json(result)

        elif path == "/api/auth/login":
            username = payload.get("username", "")
            password = payload.get("password", "")
            result = db.login_user(username, password)
            self._send_json(result)

        elif path == "/api/auth/logout":
            auth_header = self.headers.get("Authorization", "")
            token = auth_header.split("Bearer ")[1].strip() if auth_header.startswith("Bearer ") else ""
            db.logout_user(token)
            self._send_json({"success": True})

        elif path == "/api/chat":
            user = self._get_auth_user()
            question = payload.get("question", "").strip()
            history = payload.get("history", [])
            model_override = payload.get("model")
            system_override = payload.get("system_instructions")
            conversation_id = payload.get("conversation_id")

            if not question:
                result = {"success": False, "error": "Question is empty."}
            else:
                user_id = user["id"] if user else None

                if user_id and not conversation_id:
                    conv = db.create_conversation(user_id, question[:40] or "New Chat")
                    conversation_id = conv["id"]

                if user_id and conversation_id:
                    db.add_message(user_id, conversation_id, "user", question)

                result = query_openai(
                    question=question,
                    history=history,
                    model_override=model_override,
                    system_instructions=system_override,
                    user_id=user_id,
                )

                if result.get("success") and user_id and conversation_id:
                    db.add_message(user_id, conversation_id, "assistant", result["answer"])
                    result["conversation_id"] = conversation_id

            self._send_json(result)

        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    # ------------------------------------------------------------------
    # DELETE routes
    # ------------------------------------------------------------------

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        user = self._get_auth_user()
        if not user:
            self._send_json({"success": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

        if path.startswith("/api/conversations/"):
            conv_id = path.split("/api/conversations/")[1]
            success = db.delete_conversation(user["id"], conv_id)
            self._send_json({"success": success})
        elif path == "/api/memories":
            db.clear_user_memories(user["id"])
            self._send_json({"success": True})
        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    def log_message(self, format, *args):
        pass  # Silence default HTTP access logging


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def find_available_port(start_port: int = 5000, max_attempts: int = 10) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    port = find_available_port(5000)
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, RequestHandler)
    url = f"http://127.0.0.1:{port}"

    #print("=" * 60)
    print("              ✦ Q&A AI Assistant ✦")
    #print("=" * 60)
    print(f"  Server : {url}")
    print(f"  Model  : {MODEL}")
    print("  Press Ctrl+C to stop.")
    #print("=" * 60)

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server. Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    main()
