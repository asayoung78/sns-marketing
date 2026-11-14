"""이미지·영상을 공개 주소(URL)로 만든다. Instagram API는 URL로만 미디어를 받는다.

- github     : 저장소의 `media-store` 브랜치에 올리고 raw 주소를 쓴다(공개 저장소 필요).
               브랜치는 매번 커밋 1개로 새로 만들어 강제 푸시하고, 오래된 파일은 지워 용량이 쌓이지 않게 한다.
- cloudinary : Cloudinary 계정에 업로드한다.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import require_env

BRANCH = "media-store"
KEEP_DAYS = 14


def public_urls(paths: list[Path], method: str, subdir: str) -> list[str]:
    """subdir 예: 20261118-reel-12 (앞 8자리 날짜로 오래된 파일을 정리한다)."""
    if method == "github":
        return _github_store(paths, subdir)
    if method == "cloudinary":
        return [_cloudinary_upload(p) for p in paths]
    raise ValueError(f"알 수 없는 hosting.method: {method}")


def _git(cwd: Path, *args: str):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _github_store(paths: list[Path], subdir: str, attempts: int = 4) -> list[str]:
    repo = require_env("GITHUB_REPOSITORY")
    remote = f"https://x-access-token:{require_env('GITHUB_TOKEN')}@github.com/{repo}.git"
    who = ["-c", "user.name=insta-bot", "-c", "user.email=insta-bot@users.noreply.github.com"]
    for attempt in range(attempts):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "store"
            cloned = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", BRANCH, remote, str(work)],
                                    capture_output=True, text=True).returncode == 0
            if cloned:
                lease = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
                shutil.rmtree(work / ".git")  # 기존 파일만 두고 기록 없이 새로 시작(용량 누적 방지)
            else:
                lease = ""  # 브랜치가 아직 없어야 함
                work.mkdir()
            _git(work, "init", "-q")
            cutoff = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
            for d in work.iterdir():
                if d.is_dir() and d.name[:8].isdigit() and d.name[:8] < cutoff:
                    shutil.rmtree(d)
            target = work / subdir
            target.mkdir(parents=True, exist_ok=True)
            for p in paths:
                shutil.copy2(p, target / p.name)
            _git(work, *who, "checkout", "-q", "-b", BRANCH)
            _git(work, "add", "-A")
            _git(work, *who, "commit", "-q", "-m", f"미디어 저장 {subdir}")
            # 다른 작업이 그사이 올렸으면 덮어쓰지 않고 다시 시도
            pushed = subprocess.run(["git", "push", "-q", f"--force-with-lease={BRANCH}:{lease}", remote, f"{BRANCH}:{BRANCH}"],
                                    cwd=work, capture_output=True, text=True).returncode == 0
        if pushed:
            stamp = int(time.time())  # 같은 이름 파일을 바꿨을 때 캐시를 피하기 위한 꼬리표
            return [f"https://raw.githubusercontent.com/{repo}/{BRANCH}/{subdir}/{p.name}?v={stamp}" for p in paths]
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("미디어 저장소(media-store 브랜치)에 올리지 못했습니다.")


def _cloudinary_upload(path: Path) -> str:
    cloud = require_env("CLOUDINARY_CLOUD_NAME")
    api_key = require_env("CLOUDINARY_API_KEY")
    secret = require_env("CLOUDINARY_API_SECRET")
    folder = os.environ.get("CLOUDINARY_FOLDER", "instagram")
    timestamp = str(int(time.time()))
    signature = hashlib.sha1(f"folder={folder}&timestamp={timestamp}{secret}".encode()).hexdigest()
    kind = "video" if path.suffix.lower() in (".mp4", ".mov") else "image"
    with open(path, "rb") as f:
        resp = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/{kind}/upload",
            data={"api_key": api_key, "timestamp": timestamp, "folder": folder, "signature": signature},
            files={"file": f},
            timeout=600,
        )
    if not resp.ok:
        raise RuntimeError(f"Cloudinary 업로드 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json()["secure_url"]
