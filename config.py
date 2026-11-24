import os
from dotenv import load_dotenv

load_dotenv()


def get_config_val(key: str, default: str = "") -> str:
    """Retrieves configuration value from Streamlit Secrets or Environment Variables."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


# 1. LLM provider: "gemini" (OpenAI-compatible, default) or "anthropic" (direct Anthropic Messages API)
LLM_PROVIDER = get_config_val("LLM_PROVIDER", "gemini").strip().lower()

# 2. Google AI Studio API Key (loaded securely from .env or st.secrets)
LLM_API_KEY = get_config_val("LLM_API_KEY", "")

# 3. Gemini OpenAI-compatible base URL
LLM_BASE_URL = get_config_val("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

# 4. Model name (default: gemini-2.5-flash; e.g. claude-haiku-5-5 when LLM_PROVIDER=anthropic)
LLM_MODEL = get_config_val("LLM_MODEL", "gemini-2.5-flash")

# 5. Anthropic API key (used only when LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY = get_config_val("ANTHROPIC_API_KEY", "")

# 4. Optional Beta Passkey protection (leave empty to disable gate)
BETA_ACCESS_CODE = get_config_val("BETA_ACCESS_CODE", "")


