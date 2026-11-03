"""Runtime settings, read from environment variables (and an optional repo-root .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

# Documented at https://dev.meta.ai/docs/api-reference (OpenAI-compatible Chat Completions).
DEFAULT_API_BASE = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    api_base: str
    model: str
    reasoning_effort: str
    timeout_s: float
    max_completion_tokens: int
    max_attempts: int
    budget_usd: float
    propagate: bool
    construct: bool
    db_path: Path
    demo_db_path: Path
    texts_dir: Path
    demo_dir: Path


def load_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    return Settings(
        api_key=os.environ.get("MODEL_API_KEY") or None,
        api_base=os.environ.get("MOTIF_API_BASE", DEFAULT_API_BASE).rstrip("/"),
        model=os.environ.get("MOTIF_MODEL", DEFAULT_MODEL),
        reasoning_effort=os.environ.get("MOTIF_REASONING_EFFORT", "medium"),
        timeout_s=float(os.environ.get("MOTIF_TIMEOUT_S", "300")),
        # Hard cap on output (visible + reasoning) tokens per call; bounds the worst-case cost.
        max_completion_tokens=int(os.environ.get("MOTIF_MAX_COMPLETION_TOKENS", "12000")),
        # 1 = no automatic retries (a failed call stops the run instead of silently re-spending).
        max_attempts=int(os.environ.get("MOTIF_MAX_ATTEMPTS", "1")),
        # Total spend allowed across all calls recorded in the local database.
        budget_usd=float(os.environ.get("MOTIF_BUDGET_USD", "2.00")),
        # Reconsider units linked to a changed unit after each passage (one extra call at most).
        propagate=os.environ.get("MOTIF_PROPAGATE", "1") != "0",
        # Build higher-level meanings from several units when a passage triggers it (one call at most).
        construct=os.environ.get("MOTIF_CONSTRUCT", "1") != "0",
        db_path=Path(os.environ.get("MOTIF_DB", DATA_DIR / "motif.db")),
        demo_db_path=Path(os.environ.get("MOTIF_DEMO_DB", DATA_DIR / "motif_demo.db")),
        texts_dir=DATA_DIR / "texts",
        demo_dir=DATA_DIR / "demo",
    )
