import os
from dotenv import load_dotenv

load_dotenv()

# 1. Update with your actual Google AI Studio API Key
LLM_API_KEY = os.getenv("LLM_API_KEY", "AQ.Ab8RN6LucLhHSAQ-G9Im-3wHgK4kqobW-3R3BUZdaqBMgEBDoQ")

# 2. Update to the official Gemini OpenAI-compatible base URL
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

# 3. Update to a supported Gemini model name (e.g., gemini-2.5-flash or gemini-2.5-pro)
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")


