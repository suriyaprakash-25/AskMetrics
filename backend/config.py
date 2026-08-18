from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env from the repository root if present.
# Shell environment variables always take precedence (override=False).
_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env", override=True)

ROOT = _ROOT


def _positive_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")
    return value


@dataclass(frozen=True)
class Settings:
    database_path: Path = ROOT / "askmetrics.db"
    provider: str = os.getenv("ASKMETRICS_LLM_PROVIDER", "ollama").lower()
    max_result_rows: int = _positive_int("ASKMETRICS_MAX_RESULT_ROWS", 100)
    timeout_ms: int = _positive_int("ASKMETRICS_QUERY_TIMEOUT_MS", 1500)
    retry_count: int = _positive_int("ASKMETRICS_RETRY_COUNT", 1, minimum=0)
    ollama_host: str = os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")


settings = Settings()
