"""텔레그램으로 알림을 보낸다 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)."""

import html
import os

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
