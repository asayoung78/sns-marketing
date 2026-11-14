"""텔레그램으로 알림을 보낸다 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)."""

import html
import json
import os
from pathlib import Path

import requests


def esc(text: str) -> str:
    return html.escape(str(text or ""), quote=False)


def send(text: str) -> bool:
    """HTML 형식 메시지를 보낸다. 설정이 없거나 실패해도 작업은 계속한다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("텔레그램 설정 없음 → 알림 생략")
        return False
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30, json={
            "chat_id": chat, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True})
        if not resp.ok:
            print(f"텔레그램 전송 실패 {resp.status_code}: {resp.text[:200]}")
        return resp.ok
    except Exception as e:
        print(f"텔레그램 전송 실패: {type(e).__name__}")  # 토큰이 섞여 나오지 않게 종류만
        return False


def _bot() -> tuple[str, str]:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def send_plain(text: str) -> bool:
    """서식 없이 보내기(인스타 본문처럼 길게 눌러 그대로 복사할 글)."""
    token, chat = _bot()
    if not token or not chat:
        return False
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                             json={"chat_id": chat, "text": text[:4096], "disable_web_page_preview": True})
        return resp.ok
    except Exception as e:
        print(f"텔레그램 전송 실패: {type(e).__name__}")
        return False


def send_files(paths: list[Path], caption: str = "", video: bool = False) -> bool:
    """완성본을 원본 화질 그대로 보낸다. video=True면 영상 1개, 아니면 사진들을 파일 묶음(최대 10개)으로."""
    token, chat = _bot()
    if not token or not chat:
        print("텔레그램 설정 없음 → 파일 전송 생략")
        return False
    base = f"https://api.telegram.org/bot{token}"
    try:
        if video:
            with open(paths[0], "rb") as f:
                resp = requests.post(f"{base}/sendVideo", timeout=300, files={"video": f},
                                     data={"chat_id": chat, "caption": caption[:1000], "supports_streaming": "true"})
        else:
            files = {f"f{i}": open(p, "rb") for i, p in enumerate(paths[:10])}
            media = [{"type": "document", "media": f"attach://f{i}"} for i in range(len(files))]
            if caption:
                media[-1]["caption"] = caption[:1000]
            try:
                resp = requests.post(f"{base}/sendMediaGroup", timeout=300, files=files,
                                     data={"chat_id": chat, "media": json.dumps(media, ensure_ascii=False)})
            finally:
                for f in files.values():
                    f.close()
        if not resp.ok:
            print(f"텔레그램 파일 전송 실패 {resp.status_code}: {resp.text[:200]}")
        return resp.ok
    except Exception as e:
        print(f"텔레그램 파일 전송 실패: {type(e).__name__}")
        return False
