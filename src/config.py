import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Load environment configuration
load_dotenv(BASE_DIR / ".env", override=True)

# LLM / API Configuration
API_KEY  = os.getenv("OPENAI_API_KEY", "").strip()
BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
MODEL    = os.getenv("OPENAI_MODEL", "gemini-3.8-flash").strip()

# Auto-detect provider from key prefix
if API_KEY.startswith("gsk_") and not BASE_URL:
    # Groq
    BASE_URL = "https://api.groq.com/openai/v1"
# Gemini keys (AQ.) already carry BASE_URL in .env — nothing to auto-set

# PostgreSQL Database Configuration
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE", "q&a_ai_database")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")

# SQLite Fallback Path
SQLITE_DB_PATH = str(BASE_DIR / "qa_ai.db")

# Default AI Persona Instructions
DEFAULT_SYSTEM_INSTRUCTIONS = """You are Q&A AI, an intelligent, accurate, and concise question-answering assistant.
- Answer questions directly, clearly, and thoroughly.
- Format code blocks using appropriate syntax identifiers.
- Explain concepts with helpful step-by-step examples when relevant.
- Remember and respect user preferences, profile details, and memories.
- Be polite, professional, and helpful."""

