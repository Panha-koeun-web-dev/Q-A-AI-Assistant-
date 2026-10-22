import os
import time
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

from src import db
from src.config import DEFAULT_SYSTEM_INSTRUCTIONS


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


def extract_potential_memories(user_id: int, question: str):
    """Simple heuristic to remember key personal facts shared by the user."""
    lower = question.lower().strip()
    if lower.startswith("my name is ") or "call me " in lower:
        name = question.split("is ")[-1].split(".")[0].strip() if "is " in lower else question.split("call me ")[-1].split(".")[0].strip()
        if len(name) < 30:
            db.set_user_memory(user_id, "name", name.title())
    elif "i prefer " in lower or "i like " in lower:
        pref = question.strip()[:100]
        db.set_user_memory(user_id, f"preference_{int(time.time()) % 1000}", pref)
    elif "i am learning " in lower:
        learning = lower.split("i am learning ")[-1].split(".")[0].strip()
        db.set_user_memory(user_id, "learning_topic", learning)


def query_openai(question, history=None, model_override=None, system_instructions=None, user_id=None):
    """Sends user query and message history with dynamic active model fallback and memory integration."""
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
    base_instructions = system_instructions or DEFAULT_SYSTEM_INSTRUCTIONS

    # Integrate PostgreSQL user memory if user is authenticated
    if user_id:
        memories = db.get_user_memories(user_id)
        if memories:
            memory_context = "\n".join([f"- {k}: {v}" for k, v in memories.items()])
            active_instructions = f"{base_instructions}\n\n[Persistent User Memory / Account Context]:\n{memory_context}"
        else:
            active_instructions = base_instructions
        extract_potential_memories(user_id, question)
    else:
        active_instructions = base_instructions

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

