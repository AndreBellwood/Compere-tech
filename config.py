import os
from dotenv import load_dotenv

load_dotenv()
LLM_API_KEY = os.getenv("LLM_API_KEY", "AQ.Ab8RN6LucLhHSAQ-G9Im-3wHgK4kqobW-3R3BUZdaqBMgEBDoQ")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash")