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


# 1. Google AI Studio API Key (loaded securely from .env or st.secrets)
LLM_API_KEY = get_config_val("LLM_API_KEY", "")

# 2. Gemini OpenAI-compatible base URL
LLM_BASE_URL = get_config_val("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

# 3. Supported Gemini model name (default: gemini-2.5-flash)
LLM_MODEL = get_config_val("LLM_MODEL", "gemini-2.5-flash")

# 4. Optional Beta Passkey protection (leave empty to disable gate)
BETA_ACCESS_CODE = get_config_val("BETA_ACCESS_CODE", "")


