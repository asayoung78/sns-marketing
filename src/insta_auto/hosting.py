"""이미지를 공개 주소(URL)로 만든다. Instagram API는 URL로만 이미지를 받는다."""

import hashlib
import os
import subprocess
import time
from pathlib import Path

import requests

from .config import ROOT, require_env


def public_urls(paths: list[Path], method: str) -> list[str]:
    if method == "github":
        return [_github_raw_url(p) for p in paths]
    if method == "cloudinary":
        return [_cloudinary_upload(p) for p in paths]
    raise ValueError(f"알 수 없는 hosting.method: {method}")


def _github_raw_url(path: Path) -> str:
    # 워크플로가 이미지를 먼저 커밋·푸시한 뒤 호출된다. 공개 저장소에서만 동작.
    repo = require_env("GITHUB_REPOSITORY")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    rel = path.resolve().relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{rel}"


def _cloudinary_upload(path: Path) -> str:
    cloud = require_env("CLOUDINARY_CLOUD_NAME")
    api_key = require_env("CLOUDINARY_API_KEY")
    secret = require_env("CLOUDINARY_API_SECRET")
    folder = os.environ.get("CLOUDINARY_FOLDER", "instagram")
    timestamp = str(int(time.time()))
    signature = hashlib.sha1(f"folder={folder}&timestamp={timestamp}{secret}".encode()).hexdigest()
    with open(path, "rb") as f:
        resp = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/image/upload",
            data={"api_key": api_key, "timestamp": timestamp, "folder": folder, "signature": signature},
            files={"file": f},
            timeout=120,
        )
    if not resp.ok:
        raise RuntimeError(f"Cloudinary 업로드 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json()["secure_url"]
