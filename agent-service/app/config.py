import os

from dotenv import load_dotenv

# Real environment variables win over .env, so production settings are never overridden.
load_dotenv()

AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "session")
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "0") == "1"
CURRENCY = os.getenv("CURRENCY", "USD")
VAT_PERCENT = int(os.getenv("VAT_PERCENT", "16"))
LABOUR_RATE_CENTS = int(os.getenv("LABOUR_RATE_CENTS", "3000"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "rules")
