# ✦ Q&A AI Assistant

A fast, browser-based AI assistant with **PostgreSQL** user accounts, authentication, persistent chat history, and long-term memory.

## 🗂 Project Structure

```
my_ai_assistant/
├── run.py               # Entry point — start the web server
├── .env                 # API keys & DB config (not committed)
├── requirements.txt     # Python dependencies
├── logo.jpg             # App logo
│
├── src/                 # Python backend modules
│   ├── config.py        # Centralized settings
│   ├── db.py            # Database layer (PostgreSQL + SQLite fallback)
│   └── ai_service.py    # OpenAI/Groq AI client & memory integration
│
├── templates/
│   └── index.html       # Single-page app HTML template
│
├── static/
│   ├── css/style.css    # App styles (light + dark mode)
│   ├── js/app.js        # Frontend JavaScript
│   └── images/logo.jpg  # Logo asset
│
└── archive/             # Legacy entry points (not active)
    ├── app.py           # Old Streamlit UI
    ├── gui.py           # Old Tkinter desktop UI
    └── main.py          # Old CLI interface
```

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```env
OPENAI_API_KEY=gsk_your_groq_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b


```

### 3. Run
```bash
python run.py
```

Then open `http://127.0.0.1:5000` in your browser.

## ✨ Features

- 🔐 **User accounts** with secure PBKDF2 password hashing
- 💾 **PostgreSQL chat history** with per-thread conversation management
- 🧠 **Persistent user memory** — AI remembers your name, preferences, and learning topics
- 🎨 **Light & Dark mode** with high-contrast code blocks and syntax highlighting
- 📱 **Responsive design** with collapsible sidebar (desktop + mobile)
- 🚀 **Auto model fallback** — tries multiple Groq models if one fails

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key (Groq free key starts with `gsk_`) |
| `OPENAI_BASE_URL` | API base URL (default: Groq) |
| `OPENAI_MODEL` | Model name (default: `openai/gpt-oss-20b`) |
| `PGHOST` | PostgreSQL host |
| `PGPORT` | PostgreSQL port |
| `PGDATABASE` | Database name |
| `PGUSER` | Database user |
| `PGPASSWORD` | Database password |

> **No PostgreSQL?** The app automatically falls back to a local SQLite database (`qa_ai.db`).
