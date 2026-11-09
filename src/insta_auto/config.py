"""settings.toml과 환경 변수(GitHub Secrets)를 읽는다."""

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "history.json"
MEDIA_DIR = ROOT / "media"


def load_settings() -> dict:
    with open(ROOT / "settings.toml", "rb") as f:
        return tomllib.load(f)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"환경 변수 {name} 가 비어 있습니다. GitHub Secrets 설정을 확인하세요.")
    return value
