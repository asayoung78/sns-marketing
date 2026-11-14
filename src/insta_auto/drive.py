"""구글 드라이브 링크 공유 폴더에서 영상·음악을 찾아 내려받는다 (GDRIVE_API_KEY, GDRIVE_FOLDER_ID)."""

import os
import re
from pathlib import Path

import requests

API = "https://www.googleapis.com/drive/v3/files"
MUSIC_FOLDER = "음악"


def folder_id(raw: str) -> str:
    """폴더 주소 전체를 넣어도 ID만 뽑아낸다 (예: .../folders/1AbC...?usp=sharing → 1AbC...)."""
    m = re.search(r"folders/([A-Za-z0-9_-]+)", raw) or re.search(r"[A-Za-z0-9_-]{15,}", raw)
    return m.group(1) if m and m.groups() else (m.group(0) if m else "")


def _key() -> str:
    return os.environ.get("GDRIVE_API_KEY", "").strip()


def _root() -> str:
    return folder_id(os.environ.get("GDRIVE_FOLDER_ID", ""))


def list_files(parent: str = "") -> list[dict]:
    parent = parent or _root()
    if not _key() or not parent:
        return []
    resp = requests.get(API, timeout=30, params={
        "q": f"'{parent}' in parents and trashed = false", "key": _key(),
        "fields": "files(id,name,mimeType,size,modifiedTime)", "pageSize": 200, "orderBy": "modifiedTime desc"})
    resp.raise_for_status()
    return resp.json().get("files", [])


def download(file: dict, dest: Path) -> Path:
    with requests.get(f"{API}/{file['id']}", params={"alt": "media", "key": _key()}, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return dest


def find_video(number: int) -> dict | None:
    """파일 이름이 '초안번호_'로 시작하는 영상 (예: 12_부산포.mp4). 여러 개면 가장 최근 것."""
    for f in list_files():
        if f["mimeType"].startswith("video/") and re.match(rf"^{number}[_\-\s.]", f["name"]):
            return f
    return None


def music_tracks() -> list[dict]:
    folder = next((f for f in list_files() if f["mimeType"].endswith("folder") and f["name"] == MUSIC_FOLDER), None)
    if not folder:
        return []
    tracks = [f for f in list_files(folder["id"]) if f["mimeType"].startswith("audio/")]
    return sorted(tracks, key=lambda f: f["name"])
