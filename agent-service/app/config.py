import os

from dotenv import load_dotenv

# Real environment variables win over .env, so production settings are never overridden.
load_dotenv()

# Shared ONLY between the Next.js server and this service. Next.js mints a short-lived
# token with it; it is deliberately different from the browser session secret (AUTH_SECRET).
AGENT_SERVICE_SECRET = os.getenv("AGENT_SERVICE_SECRET", "")
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "0") == "1"
CURRENCY = os.getenv("CURRENCY", "USD")
VAT_PERCENT = int(os.getenv("VAT_PERCENT", "16"))
LABOUR_RATE_CENTS = int(os.getenv("LABOUR_RATE_CENTS", "3000"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "rules")
DATABASE_URL = os.getenv("DATABASE_URL", "")  # Neon connection string; enables persistent run storage

if not AUTH_DISABLED and len(AGENT_SERVICE_SECRET) < 32:
    raise RuntimeError("Set AGENT_SERVICE_SECRET (32+ chars), or AUTH_DISABLED=1 for local development only")
