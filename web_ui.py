import json
import os
import socket
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
    AuthenticationError,
    NotFoundError,
    BadRequestError,
)

# Load configuration
load_dotenv(override=True)
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b").strip()

if API_KEY.startswith("gsk_") and not BASE_URL:
    BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_SYSTEM_INSTRUCTIONS = """You are Q&A AI, an intelligent, accurate, and concise question-answering assistant.
- Answer questions directly, clearly, and thoroughly.
- Format code blocks using appropriate syntax identifiers.
- Explain concepts with helpful step-by-step examples when relevant.
- Be polite, professional, and helpful."""


def get_openai_client(base_url=None):
    load_dotenv(override=True)
    current_key = os.getenv("OPENAI_API_KEY", "").strip()
    current_base = base_url or os.getenv("OPENAI_BASE_URL", "").strip() or None
    if current_key.startswith("gsk_") and not current_base:
        current_base = "https://api.groq.com/openai/v1"
    return OpenAI(
        api_key=current_key or "missing-key",
        base_url=current_base,
        timeout=60.0,
        max_retries=2,
    )


def query_openai(question, history=None, model_override=None, system_instructions=None):
    """Sends user query and message history with dynamic active model fallback."""
    load_dotenv(override=True)
    current_key = os.getenv("OPENAI_API_KEY", "").strip()
    current_base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    if current_key.startswith("gsk_") and not current_base:
        current_base = "https://api.groq.com/openai/v1"

    if not current_key or current_key.startswith("your_"):
        return {
            "success": False,
            "error": "⚠️ **API key is missing or invalid.** Please configure your `.env` file.",
        }

    chosen_model = model_override or os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b").strip()
    active_instructions = system_instructions or DEFAULT_SYSTEM_INSTRUCTIONS
    client = get_openai_client(current_base)

    # Build conversation payload
    messages = [{"role": "system", "content": active_instructions}]
    if history:
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    # Prioritized active models list
    models_to_try = [chosen_model]
    if current_key.startswith("gsk_") or (current_base and "groq" in current_base):
        for candidate in ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
            if candidate not in models_to_try:
                models_to_try.append(candidate)
    else:
        for candidate in ["gpt-4o-mini", "gpt-3.5-turbo"]:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

    last_error_msg = None

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            answer = response.choices[0].message.content or "Q&A AI did not return a text response."
            return {"success": True, "answer": answer, "model": model_name}

        except (NotFoundError, BadRequestError) as err:
            last_error_msg = str(err)
            continue

        except AuthenticationError:
            return {
                "success": False,
                "error": "⚠️ **Invalid API Key (401 Unauthorized)**. Check your key at https://console.groq.com/keys",
            }

        except RateLimitError as err:
            return {
                "success": False,
                "error": f"⚠️ Rate limit or quota error: {str(err)}",
            }

        except APIConnectionError:
            return {
                "success": False,
                "error": "⚠️ **Connection Error:** Unable to reach AI server. Check your internet connection.",
            }

        except APIStatusError as err:
            return {
                "success": False,
                "error": f"⚠️ **API Error ({err.status_code}):** {err.message}",
            }

        except Exception as exc:
            return {
                "success": False,
                "error": f"⚠️ **Unexpected Error:** {str(exc)}",
            }

    return {
        "success": False,
        "error": f"⚠️ **Model Error:** Could not complete request. Details: {last_error_msg}",
    }


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Q&A AI</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <style>
    :root {
      --bg-main: #090d16;
      --bg-card: #111726;
      --bg-panel: #182033;
      --bg-input: #0f1626;
      --border: rgba(255, 255, 255, 0.08);
      --border-focus: #3b82f6;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #3b82f6;
      --accent-gradient: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
      --code-bg: #141a29;
      --code-header: #0e121e;
      --code-border: rgba(255, 255, 255, 0.08);
      --code-text: #e2e8f0;
      --inline-code-bg: rgba(59, 130, 246, 0.14);
      --inline-code-text: #60a5fa;
      --copy-btn-bg: rgba(255, 255, 255, 0.08);
      --copy-btn-text: #cbd5e1;
      --shadow-lg: 0 16px 36px -10px rgba(0, 0, 0, 0.6);
      --card-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    }

    [data-theme="light"] {
      --bg-main: #f1f5f9;
      --bg-card: #ffffff;
      --bg-panel: #e2e8f0;
      --bg-input: #ffffff;
      --border: #cbd5e1;
      --border-focus: #2563eb;
      --text-main: #0f172a;
      --text-muted: #475569;
      --accent: #2563eb;
      --accent-gradient: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
      --code-bg: #f8fafc;
      --code-header: #eef2f6;
      --code-border: #cbd5e1;
      --code-text: #0f172a;
      --inline-code-bg: #e0e7ff;
      --inline-code-text: #3730a3;
      --copy-btn-bg: #ffffff;
      --copy-btn-text: #334155;
      --shadow-lg: 0 16px 36px -10px rgba(15, 23, 42, 0.08);
      --card-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background-color: var(--bg-main);
      color: var(--text-main);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transition: background-color 0.2s ease, color 0.2s ease;
    }

    /* Minimalist Navbar */
    header {
      height: 60px;
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      z-index: 10;
      flex-shrink: 0;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 800;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
    }

    .brand-icon {
      width: 34px;
      height: 34px;
      border-radius: 9px;
      background: var(--accent-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 1.05rem;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
    }

    .model-badge {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 20px;
      background: var(--bg-panel);
      border: 1px solid var(--border);
      color: var(--accent);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
      display: inline-block;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.8); }
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .btn-icon {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      color: var(--text-main);
      height: 34px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.85rem;
      font-weight: 600;
      padding: 0 12px;
      gap: 6px;
      transition: all 0.15s ease;
    }

    .btn-icon:hover {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }

    .btn-square {
      width: 34px;
      padding: 0;
    }

    /* Chat Area */
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 920px;
      width: 100%;
      margin: 0 auto;
      padding: 16px 20px;
      overflow: hidden;
    }

    #chat-container {
      flex: 1;
      overflow-y: auto;
      padding-right: 6px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      scroll-behavior: smooth;
    }

    #chat-container::-webkit-scrollbar { width: 5px; }
    #chat-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

    /* Minimalist Placeholder */
    .empty-state {
      margin: auto;
      text-align: center;
      padding: 40px 20px;
      animation: fadeIn 0.3s ease;
    }

    .empty-title {
      font-size: 1.7rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
      background: var(--accent-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .empty-sub {
      color: var(--text-muted);
      font-size: 0.95rem;
    }

    /* Message Rows */
    .message-row {
      display: flex;
      gap: 12px;
      animation: slideUp 0.2s ease forwards;
    }

    @keyframes slideUp {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.8rem;
      font-weight: 700;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .avatar-user {
      background: var(--accent-gradient);
      color: #fff;
    }

    .avatar-qa {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      color: var(--accent);
      font-size: 0.72rem;
      font-weight: 800;
    }

    .bubble-wrapper {
      flex: 1;
      max-width: 90%;
    }

    .user-row {
      flex-direction: row-reverse;
    }

    .user-row .bubble-wrapper {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .bubble {
      padding: 14px 18px;
      border-radius: 14px;
      font-size: 0.95rem;
      line-height: 1.65;
      word-break: break-word;
    }

    .user-row .bubble {
      background: var(--accent);
      color: #ffffff;
      border-bottom-right-radius: 3px;
    }

    .ai-row .bubble {
      background: var(--bg-card);
      border: 1px solid var(--border);
      color: var(--text-main);
      border-bottom-left-radius: 3px;
      box-shadow: var(--card-shadow);
    }

    .sender-name {
      font-size: 0.75rem;
      font-weight: 700;
      margin-bottom: 5px;
      color: var(--text-muted);
    }

    .bubble p:not(:last-child) { margin-bottom: 0.8em; }
    .bubble ul, .bubble ol { margin: 0.5em 0 0.8em 1.3em; }
    .bubble li { margin-bottom: 0.35em; }

    /* Inline Code */
    .bubble code:not(pre code) {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88em;
      background: var(--inline-code-bg);
      color: var(--inline-code-text);
      padding: 2px 6px;
      border-radius: 4px;
      border: 1px solid var(--border);
      font-weight: 500;
    }

    /* Code Blocks */
    .bubble pre {
      margin: 12px 0;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid var(--code-border);
      background: var(--code-bg);
      position: relative;
    }

    .code-header {
      background: var(--code-header);
      padding: 6px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--code-border);
    }

    .bubble pre code {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem;
      display: block;
      padding: 14px 16px;
      overflow-x: auto;
      background: var(--code-bg) !important;
      color: var(--code-text) !important;
      line-height: 1.55;
    }

    .copy-btn {
      background: var(--copy-btn-bg);
      border: 1px solid var(--code-border);
      color: var(--copy-btn-text);
      padding: 3px 10px;
      border-radius: 5px;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 600;
      transition: all 0.15s ease;
    }

    .copy-btn:hover {
      background: var(--accent);
      color: #ffffff;
      border-color: var(--accent);
    }

    /* High-Contrast Syntax Highlighting */
    /* Light Mode */
    [data-theme="light"] .hljs-keyword,
    [data-theme="light"] .hljs-selector-tag { color: #d946ef; font-weight: 600; }
    [data-theme="light"] .hljs-string,
    [data-theme="light"] .hljs-title { color: #0284c7; }
    [data-theme="light"] .hljs-comment,
    [data-theme="light"] .hljs-quote { color: #64748b; font-style: italic; }
    [data-theme="light"] .hljs-number,
    [data-theme="light"] .hljs-literal { color: #ea580c; font-weight: 600; }
    [data-theme="light"] .hljs-function { color: #059669; font-weight: 600; }
    [data-theme="light"] .hljs-built_in { color: #2563eb; }
    [data-theme="light"] .hljs-attr,
    [data-theme="light"] .hljs-variable { color: #7c3aed; }

    /* Dark Mode */
    :root:not([data-theme="light"]) .hljs-keyword { color: #f472b6; font-weight: 600; }
    :root:not([data-theme="light"]) .hljs-string { color: #38bdf8; }
    :root:not([data-theme="light"]) .hljs-comment { color: #64748b; font-style: italic; }
    :root:not([data-theme="light"]) .hljs-number { color: #fb923c; font-weight: 600; }
    :root:not([data-theme="light"]) .hljs-function { color: #34d399; font-weight: 600; }
    :root:not([data-theme="light"]) .hljs-built_in { color: #60a5fa; }
    :root:not([data-theme="light"]) .hljs-attr,
    :root:not([data-theme="light"]) .hljs-variable { color: #a78bfa; }

    /* Typing Dots */
    .typing-dots {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 8px 12px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
    }

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--accent);
      animation: typing 1.4s infinite ease-in-out;
    }

    .dot:nth-child(1) { animation-delay: 0s; }
    .dot:nth-child(2) { animation-delay: 0.2s; }
    .dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typing {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
      30% { transform: translateY(-5px); opacity: 1; }
    }

    /* Redesigned Input Form */
    .input-wrapper {
      padding-top: 12px;
      flex-shrink: 0;
    }

    .input-bar {
      display: flex;
      align-items: flex-end;
      background: var(--bg-card);
      border: 1.5px solid var(--border);
      border-radius: 14px;
      padding: 8px 10px;
      box-shadow: var(--shadow-lg);
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .input-bar:focus-within {
      border-color: var(--border-focus);
      box-shadow: 0 4px 20px rgba(37, 99, 235, 0.15);
    }

    textarea#question-input {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      resize: none;
      color: var(--text-main);
      font-family: inherit;
      font-size: 0.96rem;
      line-height: 1.45;
      padding: 6px 10px;
      max-height: 160px;
      min-height: 24px;
    }

    textarea#question-input::placeholder { color: var(--text-muted); }

    .submit-btn {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: var(--accent-gradient);
      color: #fff;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: all 0.15s ease;
    }

    .submit-btn:hover:not(:disabled) {
      transform: scale(1.04);
      filter: brightness(1.1);
    }

    .submit-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      transform: none;
    }

    .input-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.72rem;
      color: var(--text-muted);
      padding: 6px 4px 0;
    }

    /* Modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(4px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
    }

    .modal-backdrop.active { display: flex; }

    .modal {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 22px;
      width: 90%;
      max-width: 480px;
      box-shadow: var(--shadow-lg);
    }

    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .modal-title { font-size: 1.1rem; font-weight: 700; }
    .form-group { margin-bottom: 14px; }
    .form-label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 6px; color: var(--text-muted); }

    .form-control {
      width: 100%;
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 12px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 0.88rem;
      outline: none;
    }

    .form-control:focus { border-color: var(--accent); }
    .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }

    .btn-secondary {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 7px 14px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
    }

    .btn-primary {
      background: var(--accent-gradient);
      border: none;
      color: white;
      padding: 7px 16px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
    }
  </style>
</head>
<body>

  <!-- Minimalist Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">Q&A</div>
      <div>Q&A AI</div>
      <div class="model-badge">
        <span class="status-dot"></span>
        <span id="active-model-display">""" + MODEL + """</span>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn-icon" id="clear-chat-btn" title="Clear Conversation">
        <span>🗑️</span>
        <span>Clear</span>
      </button>
      <button class="btn-icon btn-square" id="settings-btn" title="Settings">⚙️</button>
      <button class="btn-icon btn-square" id="theme-btn" title="Toggle Theme">🌙</button>
    </div>
  </header>

  <!-- Clean Chat Surface -->
  <main>
    <div id="chat-container">
      <div class="empty-state" id="empty-state">
        <h1 class="empty-title">Q&A AI</h1>
        <p class="empty-sub">Type any question below to get an instant answer.</p>
      </div>
    </div>

    <!-- Question Input Bar -->
    <div class="input-wrapper">
      <div class="input-bar">
        <textarea
          id="question-input"
          placeholder="Ask Q&A AI any question... (Press Enter to submit)"
          rows="1"
        ></textarea>
        <button class="submit-btn" id="send-btn" title="Submit Question">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      <div class="input-footer">
        <span>Q&A AI Assistant</span>
        <span>Enter ↵ to submit • Shift + Enter for newline</span>
      </div>
    </div>
  </main>

  <!-- Settings Modal -->
  <div class="modal-backdrop" id="settings-modal">
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">⚙️ Q&A AI Settings</h3>
        <button class="btn-icon btn-square" onclick="closeSettingsModal()">✕</button>
      </div>
      <div class="form-group">
        <label class="form-label" for="setting-model">Active Model</label>
        <select id="setting-model" class="form-control">
          <option value="openai/gpt-oss-20b" selected>openai/gpt-oss-20b (Fast & Free)</option>
          <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b (High Capability)</option>
          <option value="openai/gpt-oss-120b">openai/gpt-oss-120b (Large Model)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label" for="setting-system">System Instructions</label>
        <textarea id="setting-system" class="form-control" rows="3">""" + DEFAULT_SYSTEM_INSTRUCTIONS + """</textarea>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeSettingsModal()">Cancel</button>
        <button class="btn-primary" onclick="saveSettings()">Save Changes</button>
      </div>
    </div>
  </div>

  <script>
    const savedTheme = localStorage.getItem('qa_ai_theme') || 'dark';

    const state = {
      history: [],
      isGenerating: false,
      model: '""" + MODEL + """',
      systemInstructions: `""" + DEFAULT_SYSTEM_INSTRUCTIONS.replace("`", "\\`") + """`,
      theme: savedTheme
    };

    const chatContainer = document.getElementById('chat-container');
    const emptyState = document.getElementById('empty-state');
    const inputEl = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const themeBtn = document.getElementById('theme-btn');
    const clearBtn = document.getElementById('clear-chat-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');

    // Apply saved theme immediately
    document.documentElement.setAttribute('data-theme', state.theme);
    themeBtn.textContent = state.theme === 'dark' ? '🌙' : '☀️';

    marked.setOptions({
      highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
      },
      breaks: true
    });

    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuestion();
      }
    });

    sendBtn.addEventListener('click', submitQuestion);
    clearBtn.addEventListener('click', clearChat);
    settingsBtn.addEventListener('click', openSettingsModal);

    themeBtn.addEventListener('click', () => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', state.theme);
      themeBtn.textContent = state.theme === 'dark' ? '🌙' : '☀️';
      localStorage.setItem('qa_ai_theme', state.theme);
    });

    function openSettingsModal() {
      settingsModal.classList.add('active');
    }

    function closeSettingsModal() {
      settingsModal.classList.remove('active');
    }

    function saveSettings() {
      state.model = document.getElementById('setting-model').value || state.model;
      state.systemInstructions = document.getElementById('setting-system').value;
      document.getElementById('active-model-display').textContent = state.model;
      closeSettingsModal();
    }

    function clearChat() {
      state.history = [];
      chatContainer.innerHTML = '';
      chatContainer.appendChild(emptyState);
      emptyState.style.display = 'block';
      inputEl.focus();
    }

    function addMessage(sender, content) {
      if (emptyState) {
        emptyState.style.display = 'none';
      }

      const isUser = (sender === 'You');
      const row = document.createElement('div');
      row.className = `message-row ${isUser ? 'user-row' : 'ai-row'}`;

      const avatar = document.createElement('div');
      avatar.className = `avatar ${isUser ? 'avatar-user' : 'avatar-qa'}`;
      avatar.textContent = isUser ? '👤' : 'Q&A';

      const wrapper = document.createElement('div');
      wrapper.className = 'bubble-wrapper';

      const senderLabel = document.createElement('div');
      senderLabel.className = 'sender-name';
      senderLabel.textContent = isUser ? 'You' : 'Q&A AI';
      wrapper.appendChild(senderLabel);

      const bubble = document.createElement('div');
      bubble.className = 'bubble';

      if (isUser) {
        bubble.textContent = content;
      } else {
        bubble.innerHTML = marked.parse(content);
        attachCopyButtons(bubble);
      }

      wrapper.appendChild(bubble);
      row.appendChild(avatar);
      row.appendChild(wrapper);
      chatContainer.appendChild(row);

      chatContainer.scrollTop = chatContainer.scrollHeight;
      return bubble;
    }

    function attachCopyButtons(container) {
      const preBlocks = container.querySelectorAll('pre');
      preBlocks.forEach((pre) => {
        const code = pre.querySelector('code');
        const lang = (code.className.match(/language-(\\w+)/) || [, 'code'])[1];

        const header = document.createElement('div');
        header.className = 'code-header';
        header.innerHTML = `<span>${lang}</span><button class="copy-btn">Copy</button>`;

        const copyBtn = header.querySelector('.copy-btn');
        copyBtn.addEventListener('click', async () => {
          await navigator.clipboard.writeText(code.innerText);
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
        });

        pre.insertBefore(header, code);
      });
    }

    function showTypingIndicator() {
      const row = document.createElement('div');
      row.id = 'typing-indicator-row';
      row.className = 'message-row ai-row';
      row.innerHTML = `
        <div class="avatar avatar-qa">Q&A</div>
        <div class="bubble-wrapper">
          <div class="sender-name">Q&A AI</div>
          <div class="typing-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      `;
      chatContainer.appendChild(row);
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function removeTypingIndicator() {
      const indicator = document.getElementById('typing-indicator-row');
      if (indicator) indicator.remove();
    }

    async function submitQuestion() {
      const question = inputEl.value.trim();
      if (!question || state.isGenerating) return;

      state.isGenerating = true;
      sendBtn.disabled = true;
      inputEl.value = '';
      inputEl.style.height = 'auto';

      addMessage('You', question);
      showTypingIndicator();

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: question,
            history: state.history,
            model: state.model,
            system_instructions: state.systemInstructions
          })
        });

        const data = await response.json();
        removeTypingIndicator();

        if (data.success) {
          if (data.model && data.model !== state.model) {
            state.model = data.model;
            document.getElementById('active-model-display').textContent = data.model;
          }
          addMessage('Q&A AI', data.answer);
          state.history.push({ role: 'user', content: question });
          state.history.push({ role: 'assistant', content: data.answer });
          if (state.history.length > 20) state.history = state.history.slice(-20);
        } else {
          addMessage('Q&A AI', data.error || 'Failed to get answer.');
        }
      } catch (err) {
        removeTypingIndicator();
        addMessage('Q&A AI', `⚠️ **Network Error:** Could not contact server. Please ensure the server is running.`);
      } finally {
        state.isGenerating = false;
        sendBtn.disabled = false;
        inputEl.focus();
      }
    }
  </script>
</body>
</html>
"""


class RequestHandler(BaseHTTPRequestHandler):
    def _send_response(self, content_type, body_bytes, status=HTTPStatus.OK):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = HTML_CONTENT.encode("utf-8")
            self._send_response("text/html; charset=utf-8", body)
        elif parsed.path == "/api/status":
            info = {
                "status": "online",
                "model": MODEL,
                "has_api_key": bool(API_KEY),
            }
            body = json.dumps(info).encode("utf-8")
            self._send_response("application/json", body)
        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                payload = {}

            question = payload.get("question", "").strip()
            history = payload.get("history", [])
            model_override = payload.get("model")
            system_override = payload.get("system_instructions")

            if not question:
                result = {"success": False, "error": "Question is empty."}
            else:
                result = query_openai(
                    question=question,
                    history=history,
                    model_override=model_override,
                    system_instructions=system_override,
                )

            body = json.dumps(result).encode("utf-8")
            self._send_response("application/json", body)
        else:
            self._send_response("text/plain", b"404 Not Found", HTTPStatus.NOT_FOUND)

    def log_message(self, format, *args):
        pass


def find_available_port(start_port=5000, max_attempts=10):
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

    print("=" * 60)
    print("              ✦ Q&A AI (BROWSER STUDIO) ✦")
    print("=" * 60)
    print(f"Server is running at: {url}")
    print(f"Active Model:        {MODEL}")
    print("Opening application in your default browser...")
    print("Press Ctrl+C to terminate.")
    print("=" * 60)

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server. Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    main()
