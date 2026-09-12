"""Environment config. BYOK: every external capability reads its key from env.
A missing key disables the feature, it never crashes the app."""
import os

DB_PATH = os.environ.get("MARKETERLOOP_DB", "./data/marketerloop.db")
MODEL = os.environ.get("MARKETERLOOP_MODEL", "openrouter/anthropic/claude-sonnet-4.5")
MOCK_LLM = os.environ.get("MOCK_LLM", "0") == "1"

def llm_key_present() -> bool:
    return any(os.environ.get(k) for k in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"))
