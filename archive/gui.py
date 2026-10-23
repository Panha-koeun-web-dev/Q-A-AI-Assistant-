import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
    AuthenticationError,
    NotFoundError,
)

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b").strip()
BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None

# Auto-detect Groq keys
if API_KEY.startswith("gsk_") and not BASE_URL:
    BASE_URL = "https://api.groq.com/openai/v1"

if MODEL == "gpt-4.1-mini" and not BASE_URL:
    MODEL = "gpt-4o-mini"

SYSTEM_INSTRUCTIONS = """You are QA AI Assistant, built by Panha Koeun.
- Your name is QA AI Assistant.
- You were built and developed by Panha Koeun.
- If asked who you are, what your name is, or who created you, always introduce yourself as QA AI Assistant built by Panha Koeun. Never call yourself ChatGPT or claim to be built by OpenAI.
- Answer questions clearly and accurately.
- Explain difficult topics in simple English.
- Help with Python, programming, technology, and learning.
- Provide examples and step-by-step instructions when useful.
- Admit when you are uncertain.
- Never claim to have performed actions you did not perform.
- Do not ask the user to reveal passwords or secret API keys."""

conversation = []
client = None

if API_KEY:
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=60.0,
        max_retries=2,
    )


def query_ai_backend(question):
    """Sends question to AI provider and returns answer."""
    global client
    if not client or not API_KEY:
        return (
            "⚠️ Error: OPENAI_API_KEY is missing or invalid in your .env file.\n\n"
            "To get a 100% free key:\n"
            "1. Visit https://console.groq.com/keys\n"
            "2. Add to .env: OPENAI_API_KEY=gsk_... and OPENAI_BASE_URL=https://api.groq.com/openai/v1"
        )

    conversation.append({"role": "user", "content": question})

    try:
        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}] + conversation
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )
            answer = response.choices[0].message.content or "The AI did not return a text answer."
        except (AttributeError, TypeError):
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_INSTRUCTIONS,
                input=conversation,
                store=False,
            )
            answer = response.output_text or "The AI did not return a text answer."

        conversation.append({"role": "assistant", "content": answer})
        if len(conversation) > 20:
            del conversation[:-20]

        return answer

    except AuthenticationError:
        conversation.pop()
        return "⚠️ Authentication error: The provided API key was rejected."

    except NotFoundError as err:
        conversation.pop()
        return f"⚠️ Model '{MODEL}' not found. Please check model name in .env."

    except RateLimitError as err:
        conversation.pop()
        err_msg = str(err)
        if "insufficient_quota" in err_msg or "quota" in err_msg:
            return (
                "⚠️ OpenAI Quota Exceeded ($0 balance).\n\n"
                "Get a 100% FREE key from Groq:\n"
                "1. Go to https://console.groq.com/keys\n"
                "2. Set in .env:\n"
                "   OPENAI_API_KEY=gsk_...\n"
                "   OPENAI_BASE_URL=https://api.groq.com/openai/v1\n"
                "   OPENAI_MODEL=llama-3.3-70b-versatile"
            )
        return f"⚠️ Rate limit error: {err_msg}"

    except APIConnectionError:
        conversation.pop()
        return "⚠️ Cannot connect to the AI service. Check your internet connection."

    except APIStatusError as err:
        conversation.pop()
        return f"⚠️ The AI service returned an error (status {err.status_code})."

    except Exception as exc:
        conversation.pop()
        return f"⚠️ An error occurred: {exc}"


class AIAssistantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 Q&A AI")
        self.geometry("780x640")
        self.minsize(550, 450)

        self.style = ttk.Style(self)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self.create_widgets()

        if not API_KEY:
            messagebox.showwarning(
                "API Key Warning",
                "OPENAI_API_KEY was not found in your environment or .env file.\n"
                "Please add it to enable AI responses.",
            )

    def create_widgets(self):
        header_frame = tk.Frame(self, bg="#20232a", pady=10, padx=14)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="🤖 My AI Assistant",
            font=("Segoe UI", 14, "bold"),
            fg="#61dafb",
            bg="#20232a",
        )
        title_label.pack(side=tk.LEFT)

        model_label = tk.Label(
            header_frame,
            text=f"Model: {MODEL}",
            font=("Segoe UI", 9),
            fg="#abb2bf",
            bg="#20232a",
        )
        model_label.pack(side=tk.RIGHT, pady=4)

        chat_frame = tk.Frame(self, padx=12, pady=8)
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_display = ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            state=tk.DISABLED,
            bg="#ffffff",
            padx=10,
            pady=10,
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        self.chat_display.tag_config(
            "user_header",
            foreground="#0b5ed7",
            font=("Segoe UI", 10, "bold"),
            spacing1=8,
            spacing3=2,
        )
        self.chat_display.tag_config(
            "ai_header",
            foreground="#198754",
            font=("Segoe UI", 10, "bold"),
            spacing1=8,
            spacing3=2,
        )
        self.chat_display.tag_config(
            "user_message",
            foreground="#212529",
            lmargin1=12,
            lmargin2=12,
        )
        self.chat_display.tag_config(
            "ai_message",
            foreground="#212529",
            lmargin1=12,
            lmargin2=12,
        )
        self.chat_display.tag_config(
            "system_info",
            foreground="#6c757d",
            font=("Segoe UI", 9, "italic"),
        )

        self.append_system_message("Welcome! Type your question below and press Submit (or Enter).")

        input_frame = tk.Frame(self, padx=12, pady=8)
        input_frame.pack(fill=tk.X)

        self.input_entry = tk.Text(
            input_frame,
            height=3,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=6,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.input_entry.bind("<Return>", self.on_enter_pressed)
        self.input_entry.focus_set()

        btn_frame = tk.Frame(input_frame)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.submit_btn = tk.Button(
            btn_frame,
            text="Submit 💬",
            font=("Segoe UI", 10, "bold"),
            bg="#0d6efd",
            fg="#ffffff",
            activebackground="#0b5ed7",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            command=self.submit_question,
            cursor="hand2",
        )
        self.submit_btn.pack(fill=tk.X, pady=(0, 4))

        self.clear_btn = tk.Button(
            btn_frame,
            text="Clear",
            font=("Segoe UI", 9),
            bg="#e9ecef",
            fg="#495057",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            command=self.clear_conversation,
            cursor="hand2",
        )
        self.clear_btn.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(
            self,
            textvariable=self.status_var,
            font=("Segoe UI", 8),
            fg="#6c757d",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padx=8,
            pady=2,
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_enter_pressed(self, event):
        if event.state & 0x0001:
            return None
        self.submit_question()
        return "break"

    def append_system_message(self, text):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{text}\n\n", "system_info")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def append_message(self, sender, text):
        self.chat_display.config(state=tk.NORMAL)
        if sender == "You":
            self.chat_display.insert(tk.END, "You:\n", "user_header")
            self.chat_display.insert(tk.END, f"{text}\n\n", "user_message")
        else:
            self.chat_display.insert(tk.END, "AI Assistant:\n", "ai_header")
            self.chat_display.insert(tk.END, f"{text}\n\n", "ai_message")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def submit_question(self):
        question = self.input_entry.get("1.0", tk.END).strip()
        if not question:
            return

        self.input_entry.delete("1.0", tk.END)
        self.append_message("You", question)

        self.submit_btn.config(state=tk.DISABLED)
        self.status_var.set("AI is thinking...")

        threading.Thread(
            target=self._async_fetch_answer,
            args=(question,),
            daemon=True,
        ).start()

    def _async_fetch_answer(self, question):
        answer = query_ai_backend(question)
        self.after(0, self._render_answer, answer)

    def _render_answer(self, answer):
        self.append_message("AI Assistant", answer)
        self.submit_btn.config(state=tk.NORMAL)
        self.status_var.set("Ready")
        self.input_entry.focus_set()

    def clear_conversation(self):
        conversation.clear()
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.append_system_message("Conversation cleared. Type a new question to start again.")
        self.status_var.set("Conversation cleared.")


def main():
    app = AIAssistantApp()
    app.mainloop()


if __name__ == "__main__":
    main()
