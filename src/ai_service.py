"""
src/ai_service.py
-----------------
AI client — supports Google Gemini, Groq, and standard OpenAI endpoints.
Uses the OpenAI-compatible REST API interface (all providers support it).
"""
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
from src.document_service import process_attachment

# ---------------------------------------------------------------------------
# Gemini models available via OpenAI-compatible endpoint
# ---------------------------------------------------------------------------
GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# Groq fallback models
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
]


def _detect_provider(api_key: str, base_url: str) -> str:
    """Returns the active provider name: 'gemini', 'groq', or 'openai'."""
    if base_url and "googleapis" in base_url:
        return "gemini"
    if api_key.startswith("gsk_") or (base_url and "groq" in base_url):
        return "groq"
    return "openai"


def get_ai_client(api_key: str, base_url: str) -> OpenAI:
    """Creates an OpenAI-compatible client for the configured provider."""
    # Auto-set Groq base URL if not already set
    if api_key.startswith("gsk_") and not base_url:
        base_url = "https://api.groq.com/openai/v1"
    return OpenAI(
        api_key=api_key or "missing-key",
        base_url=base_url or None,
        timeout=60.0,
        max_retries=2,
    )


def extract_potential_memories(user_id: int, question: str):
    """Heuristically extracts personal facts from user messages and stores them."""
    lower = question.lower().strip()
    if lower.startswith("my name is ") or "call me " in lower:
        name = (
            question.split("is ")[-1].split(".")[0].strip()
            if "is " in lower
            else question.split("call me ")[-1].split(".")[0].strip()
        )
        if len(name) < 30:
            db.set_user_memory(user_id, "name", name.title())
    elif "i prefer " in lower or "i like " in lower:
        db.set_user_memory(user_id, f"preference_{int(time.time()) % 1000}", question.strip()[:100])
    elif "i am learning " in lower:
        learning = lower.split("i am learning ")[-1].split(".")[0].strip()
        db.set_user_memory(user_id, "learning_topic", learning)


def _build_messages(
    question: str,
    history: list,
    system_instructions: str,
    user_id: int,
    attachments: list = None,
    provider: str = "openai"
) -> list:
    """Builds the message list with system prompt, history, current question, and parsed attachments.

    Uses document_service to extract text from:
    - PDFs, Word (.docx), Excel (.xlsx), CSV, and code/text files
    - Images via Windows native OCR + metadata
    - Feeds multimodal image_url to providers supporting vision (Gemini / OpenAI)
    """
    base_sys = system_instructions or DEFAULT_SYSTEM_INSTRUCTIONS

    if user_id:
        memories = db.get_user_memories(user_id)
        if memories:
            memory_lines = "\n".join(f"- {k}: {v}" for k, v in memories.items())
            active_sys = f"{base_sys}\n\n[Persistent User Memory]:\n{memory_lines}"
        else:
            active_sys = base_sys
        extract_potential_memories(user_id, question)
    else:
        active_sys = base_sys

    # Add instruction for attachments if present
    if attachments:
        active_sys += (
            "\n\n[ATTACHED FILES INSTRUCTION]:\n"
            "The user has attached files and/or images to this message. "
            "All extracted text, documents, code, tables, and image OCR text are provided below. "
            "Analyze them carefully and answer the user's question accurately based on the contents."
        )

    messages = [{"role": "system", "content": active_sys}]
    for item in (history or []):
        role    = item.get("role", "user")
        content = item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Process each attachment via document_service
    attachment_blocks = []
    vision_image_urls = []

    for raw_att in (attachments or []):
        processed = process_attachment(raw_att)
        name = processed.get("name", "File")
        is_img = processed.get("is_image", False)
        text_content = processed.get("extracted_text", "")

        if is_img:
            if text_content and "(No text was detected" not in text_content:
                block = f"=== [ATTACHED IMAGE: {name}] ===\n{text_content}\n================================="
                attachment_blocks.append(block)

            # Send image data directly to multimodal vision models (Groq, Gemini, OpenAI)
            if processed.get("data"):
                mime_type = processed.get("type") or "image/jpeg"
                vision_image_urls.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{processed['data']}"}
                })
        else:
            block = f"=== [ATTACHED FILE: {name}] ===\n{text_content}\n================================"
            attachment_blocks.append(block)

    # Compose effective question text
    if attachment_blocks:
        attachments_context = "\n\n".join(attachment_blocks)
        effective_question = f"{attachments_context}\n\n[User Question / Instruction]:\n{question}"
    else:
        effective_question = question

    # If provider supports vision and we have image URLs
    if vision_image_urls:
        content = [{"type": "text", "text": effective_question}] + vision_image_urls
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": effective_question})

    return messages


def _get_models_to_try(provider: str, chosen_model: str, has_images: bool = False) -> list:
    """Returns an ordered list of models to try, with fallbacks.
    When images are attached, routes directly to active multimodal vision models.
    """
    if has_images:
        if provider == "groq":
            # qwen/qwen3.8-27b is Groq's active high-accuracy multimodal vision model
            return ["qwen/qwen3.8-27b"]
        elif provider == "gemini":
            vision_models = ["gemini-3.8-flash", "gemini-2.0-flash"]
            return [chosen_model] + [m for m in vision_models if m != chosen_model]
        else:
            vision_models = ["gpt-4o-mini", "gpt-4o"]
            return [chosen_model] + [m for m in vision_models if m != chosen_model]

    models = [chosen_model]
    fallbacks = {
        "gemini": GEMINI_FALLBACK_MODELS,
        "groq":   GROQ_FALLBACK_MODELS,
    }.get(provider, ["gpt-4o-mini", "gpt-3.5-turbo"])
    for m in fallbacks:
        if m not in models:
            models.append(m)
    return models


def stream_query(
    question: str,
    history: list = None,
    model_override: str = None,
    system_instructions: str = None,
    user_id: int = None,
    attachments: list = None,
):
    """
    Generator: yields text chunks as they arrive from the AI (streaming).
    Each yielded value is a string token fragment.
    Raises on unrecoverable errors (caller should catch and send error event).

    attachments: optional list of dicts with keys name, type, data (base64 str), text (str or None).
    """
    load_dotenv(override=True)
    api_key       = os.getenv("OPENAI_API_KEY", "").strip()
    base_url      = os.getenv("OPENAI_BASE_URL", "").strip() or None
    default_model = os.getenv("OPENAI_MODEL", "gemini-3.8-flash").strip()

    if not api_key or api_key.startswith("your_"):
        yield "__ERROR__⚠️ API key is missing or invalid. Please set it in your `.env` file."
        return

    provider     = _detect_provider(api_key, base_url)
    chosen_model = model_override or default_model
    has_images   = any(att.get("data") for att in (attachments or []))
    messages     = _build_messages(question, history, system_instructions, user_id, attachments, provider=provider)
    models       = _get_models_to_try(provider, chosen_model, has_images=has_images)
    client       = get_ai_client(api_key, base_url)

    for model_name in models:
        try:
            stream = client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
            )
            yield f"__MODEL__{model_name}"   # first event: which model is responding
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return  # success — stop trying models

        except (NotFoundError, BadRequestError):
            continue   # try next fallback model

        except AuthenticationError:
            yield ("__ERROR__⚠️ **Invalid API Key.** "
                   "Check https://aistudio.google.com/apikey (Gemini) "
                   "or https://console.groq.com/keys (Groq).")
            return

        except RateLimitError as err:
            yield f"__ERROR__⚠️ Rate limit exceeded: {err}"
            return

        except APIConnectionError:
            yield "__ERROR__⚠️ **Connection Error:** Cannot reach the AI server."
            return

        except APIStatusError as err:
            yield f"__ERROR__⚠️ **API Error ({err.status_code}):** {err.message}"
            return

        except Exception as exc:
            yield f"__ERROR__⚠️ **Unexpected Error:** {exc}"
            return

    yield "__ERROR__⚠️ All models failed. Please check your API key and model settings."


def query_openai(
    question: str,
    history: list = None,
    model_override: str = None,
    system_instructions: str = None,
    user_id: int = None,
    attachments: list = None,
) -> dict:
    """
    Non-streaming fallback — collects the full streamed response and returns it as a dict.
    Used internally for saving to DB after streaming completes.
    """
    load_dotenv(override=True)
    api_key       = os.getenv("OPENAI_API_KEY", "").strip()
    base_url      = os.getenv("OPENAI_BASE_URL", "").strip() or None
    default_model = os.getenv("OPENAI_MODEL", "gemini-3.8-flash").strip()

    if not api_key or api_key.startswith("your_"):
        return {"success": False, "error": "⚠️ API key missing or invalid."}

    provider     = _detect_provider(api_key, base_url)
    chosen_model = model_override or default_model
    has_images   = any(att.get("data") for att in (attachments or []))
    messages     = _build_messages(question, history, system_instructions, user_id, attachments, provider=provider)
    models       = _get_models_to_try(provider, chosen_model, has_images=has_images)
    client       = get_ai_client(api_key, base_url)
    last_error   = None

    for model_name in models:
        try:
            response = client.chat.completions.create(model=model_name, messages=messages)
            answer   = response.choices[0].message.content or "No response."
            return {"success": True, "answer": answer, "model": model_name}
        except (NotFoundError, BadRequestError) as err:
            last_error = str(err)
            continue
        except AuthenticationError:
            return {"success": False, "error": "⚠️ Invalid API Key (401)."}
        except RateLimitError as err:
            return {"success": False, "error": f"⚠️ Rate limit: {err}"}
        except APIConnectionError:
            return {"success": False, "error": "⚠️ Connection Error."}
        except APIStatusError as err:
            return {"success": False, "error": f"⚠️ API Error ({err.status_code}): {err.message}"}
        except Exception as exc:
            return {"success": False, "error": f"⚠️ Unexpected Error: {exc}"}

    return {"success": False, "error": f"⚠️ All models failed. Last: {last_error}"}
