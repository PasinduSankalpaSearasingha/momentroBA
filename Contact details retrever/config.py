import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Read OpenAI API key - check OPEN_AI_KEY (as defined in user's .env) and standard OPENAI_API_KEY
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY") or os.getenv("OPENAI_API_KEY") or ""

# Server Configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# Scraping settings
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
MAX_PAGES_PER_DOMAIN = 6
REQUEST_TIMEOUT_SECONDS = 15
