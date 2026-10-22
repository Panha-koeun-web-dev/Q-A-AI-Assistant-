import os
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

# Auto-correct model if user still has gpt-4.1-mini and no custom base url
if MODEL == "gpt-4.1-mini" and not BASE_URL:
    MODEL = "gpt-4o-mini"

if not API_KEY or API_KEY.startswith("your_"):
    raise SystemExit(
        "Error: OPENAI_API_KEY is missing or invalid in your .env file.\n"
        "To get a 100% free key, visit: https://console.groq.com/keys"
    )

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    timeout=60.0,
    max_retries=2,
)

DEFAULT_SYSTEM_INSTRUCTIONS = """You are Q&A AI, an intelligent, accurate, and concise question-answering assistant.
- Answer questions directly, clearly, and thoroughly.
- Format code blocks using appropriate syntax identifiers.
- Explain concepts with helpful step-by-step examples when relevant.
- Be polite, professional, and helpful."""

conversation = []


def ask_ai(question):
    """Send a question and recent conversation to the AI."""
    conversation.append({"role": "user", "content": question})

    try:
        # Standard chat completions (compatible with OpenAI, Groq, OpenRouter, Gemini)
        try:
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}] + conversation
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )
            answer = response.choices[0].message.content or "The AI did not return a text answer."
        except (AttributeError, TypeError):
            # Fallback to responses API if needed
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
        return "Authentication error: Your API key is invalid or unauthorized."

    except NotFoundError as err:
        conversation.pop()
        return f"Model error: {err}. Try using model 'gpt-4o-mini' or Groq's 'llama-3.3-70b-versatile'."

    except RateLimitError as err:
        conversation.pop()
        err_msg = str(err)
        if "insufficient_quota" in err_msg or "quota" in err_msg:
            return (
                "OpenAI Quota Exceeded (Account has $0 credit).\n"
                "To get a 100% FREE API key with no credit card required:\n"
                "1. Go to https://console.groq.com/keys and create a free key.\n"
                "2. Add to your .env:\n"
                "   OPENAI_API_KEY=gsk_your_groq_key_here\n"
                "   OPENAI_BASE_URL=https://api.groq.com/openai/v1\n"
                "   OPENAI_MODEL=llama-3.3-70b-versatile"
            )
        return "API rate limit or quota error. Check your usage and limits."

    except APIConnectionError:
        conversation.pop()
        return "Cannot connect to the AI service. Check your internet connection."

    except APIStatusError as error:
        conversation.pop()
        return f"The AI service returned an error (status {error.status_code})."

    except Exception as exc:
        conversation.pop()
        return f"An unexpected error occurred: {exc}"


def main():
    print("=" * 48)
    print("                   Q&A AI")
    print("=" * 48)
    print(f"Model: {MODEL}")
    print("Ask any question to begin.")
    print("Commands: /reset, /exit")
    print("-" * 48)

    while True:
        try:
            question = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not question:
            continue

        command = question.lower()

        if command == "/exit":
            print("Goodbye!")
            break

        if command == "/reset":
            conversation.clear()
            print("Conversation cleared.")
            continue

        print("\nQ&A AI: ", end="", flush=True)
        answer = ask_ai(question)
        print(answer)


if __name__ == "__main__":
    main()
