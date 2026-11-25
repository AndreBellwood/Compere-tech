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

# 4. Anthropic API key (used only when LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY = get_config_val("ANTHROPIC_API_KEY", "")

# 5. Provider-specific model defaults
GEMINI_MODEL = get_config_val("GEMINI_MODEL", "gemini-3.8-flash")
ANTHROPIC_MODEL = get_config_val("ANTHROPIC_MODEL", "claude-haiku-5-5")

# 6. Active Model name (resolved dynamically based on LLM_PROVIDER)
raw_model = get_config_val("LLM_MODEL", "").strip()
if LLM_PROVIDER == "anthropic":
    LLM_MODEL = raw_model if raw_model and "gemini" not in raw_model.lower() else ANTHROPIC_MODEL
else:
    LLM_MODEL = raw_model if raw_model and "claude" not in raw_model.lower() else GEMINI_MODEL
    # Automatically upgrade retired gemini-2.5 models if present in legacy deployment secrets
    if "2.5" in LLM_MODEL:
        LLM_MODEL = "gemini-3.8-flash"

# 7. Optional Beta Passkey protection (leave empty to disable gate)
BETA_ACCESS_CODE = get_config_val("BETA_ACCESS_CODE", "")


