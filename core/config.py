import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent

def load_env_file(env_path: Optional[Path] = None) -> dict:
    """Simple, zero-dependency .env parser that handles unquoted/quoted keys and values."""
    if env_path is None:
        env_path = BASE_DIR / ".env"
    
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            env_vars[key] = val
            # Also set in os.environ if not already set
            if key not in os.environ:
                os.environ[key] = val
            if key == "OPEN_AI_KEY" and "OPENAI_API_KEY" not in os.environ:
                os.environ["OPENAI_API_KEY"] = val
    return env_vars

# Load on module import
_loaded_env = load_env_file()

class Settings:
    def __init__(self):
        # Support both OPEN_AI_KEY (found in project .env) and standard OPENAI_API_KEY
        self.openai_api_key: str = (
            os.getenv("OPEN_AI_KEY")
            or os.getenv("OPENAI_API_KEY")
            or _loaded_env.get("OPEN_AI_KEY", "")
            or _loaded_env.get("OPENAI_API_KEY", "")
        )
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        self.request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "60"))
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
        self.aeo_geo_api_url: str = os.getenv("AEO_GEO_API_URL", "")
        self.aeo_geo_api_key: str = os.getenv("AEO_GEO_API_KEY", "")

    def validate_api_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.startswith("sk-"))

settings = Settings()
