import os
import streamlit as st
from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
    AuthenticationError,
    NotFoundError,
)

# Load environment variables
load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b").strip()

# Auto-detect Groq keys
if API_KEY.startswith("gsk_") and not BASE_URL:
    BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_SYSTEM_INSTRUCTIONS = """You are QA AI Assistant, built by Panha Koeun.
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

# Page configuration
st.set_page_config(
    page_title="Q&A AI",
    page_icon="logo.jpg" if os.path.exists("logo.jpg") else "🤖",
    layout="wide",
)

# Custom styling
st.markdown(
    """
    <style>
    .stChatInputContainer {
        padding-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state for conversation
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar options
with st.sidebar:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=90)
    st.title("⚙️ Settings")
    st.markdown("Configure your AI Assistant.")

    model = st.text_input("Model Name", value=DEFAULT_MODEL)

    system_instructions = st.text_area(
        "System Instructions",
        value=DEFAULT_SYSTEM_INSTRUCTIONS,
        height=180,
    )

    st.markdown("---")
    provider_name = "Groq (Free)" if (BASE_URL and "groq" in BASE_URL) or API_KEY.startswith("gsk_") else "OpenAI"
    st.markdown(f"**Active Provider:** `{provider_name}`")
    st.markdown(f"**Messages in conversation:** {len(st.session_state.messages)}")

    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# Main Header
st.title("✦ Q&A AI")
provider_label = "Groq Free Tier" if API_KEY.startswith("gsk_") or (BASE_URL and "groq" in BASE_URL) else "OpenAI"
st.caption(f"Powered by {provider_label} ({model}) • Ask any question to get started")

# Check for API Key
if not API_KEY or API_KEY.startswith("your_"):
    st.error("⚠️ `OPENAI_API_KEY` is missing or invalid. Please configure it in your `.env` file.")
    st.stop()

# Initialize Client with base_url
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    timeout=60.0,
    max_retries=2,
)


def call_ai(conversation_history):
    """Send conversation to AI provider and return the response."""
    formatted_input = [
        {"role": m["role"], "content": m["content"]}
        for m in conversation_history
    ]
    messages = [{"role": "system", "content": system_instructions}] + formatted_input

    try:
        # Standard Chat Completions (Groq, OpenAI, Gemini)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            return response.choices[0].message.content or "The AI did not return a text answer."
        except (AttributeError, TypeError):
            # Fallback to responses API if needed
            response = client.responses.create(
                model=model,
                instructions=system_instructions,
                input=formatted_input,
                store=False,
            )
            return response.output_text or "The AI did not return a text answer."

    except AuthenticationError:
        return "⚠️ Authentication error: Your API key was rejected. Please check your key in `.env`."
    except NotFoundError as err:
        return f"⚠️ Model Not Found: '{model}'. Details: {err}"
    except RateLimitError as err:
        return f"⚠️ Rate limit or quota error: {err}"
    except APIConnectionError:
        return "⚠️ Cannot connect to the AI service. Please check your internet connection."
    except APIStatusError as error:
        return f"⚠️ The AI service returned an error (Status code: {error.status_code})."
    except Exception as e:
        return f"⚠️ An unexpected error occurred: {str(e)}"


# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User question submission input
question = st.chat_input("Type your question here...")

if question:
    # Append and render user question
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Generate and render AI response
    with st.chat_message("assistant"):
        with st.spinner("AI is thinking..."):
            recent_context = st.session_state.messages[-20:]
            answer = call_ai(recent_context)
            st.markdown(answer)

    # Store AI response in session
    st.session_state.messages.append({"role": "assistant", "content": answer})
