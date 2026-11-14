"""Instagram API(Instagram 로그인 방식) 호출 모음."""

import time

import requests

BASE = "https://graph.instagram.com"


class InstagramClient:
    def __init__(self, token: str, api_version: str):
        self.token = token
        self.base = f"{BASE}/{api_version}"

    def _request(self, method: str, path: str, **params) -> dict:
        params["access_token"] = self.token
        resp = requests.request(method, f"{self.base}/{path}", params=params, timeout=60)
        if not resp.ok:
            # 토큰이 오류 메시지에 섞여 출력되지 않도록 본문만 보여 준다
            raise RuntimeError(f"Instagram API 오류 {resp.status_code} ({method} {path}): {resp.text[:500]}")
        return resp.json()

    # ---------- 계정 ----------
    def me(self) -> dict:
        return self._request("GET", "me", fields="user_id,username")

    # ---------- 게시 ----------
    def _wait_until_ready(self, container_id: str, timeout_s: int = 300):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            status = self._request("GET", container_id, fields="status_code").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"미디어 처리 실패: {container_id} 상태={status}")
            time.sleep(5)
        raise TimeoutError(f"미디어 처리 대기 시간 초과: {container_id}")

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        if not 2 <= len(image_urls) <= 10:
            raise ValueError("캐러셀 이미지는 2~10장이어야 합니다.")
        children = []
        for url in image_urls:
            child = self._request("POST", "me/media", image_url=url, is_carousel_item="true")["id"]
            self._wait_until_ready(child)
            children.append(child)
        container = self._request(
            "POST", "me/media", media_type="CAROUSEL", children=",".join(children), caption=caption
        )["id"]
        self._wait_until_ready(container)
        return self._request("POST", "me/media_publish", creation_id=container)["id"]

    def publish_reel(self, video_url: str, caption: str, cover_url: str = "") -> str:
        params = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
        if cover_url:
            params["cover_url"] = cover_url
        container = self._request("POST", "me/media", **params)["id"]
        self._wait_until_ready(container, timeout_s=900)  # 영상 처리는 몇 분 걸릴 수 있음
        return self._request("POST", "me/media_publish", creation_id=container)["id"]

    # ---------- 댓글 ----------
    def recent_media(self, limit: int) -> list[dict]:
        return self._request("GET", "me/media", fields="id,caption,timestamp,comments_count", limit=limit).get("data", [])

    def comments(self, media_id: str) -> list[dict]:
        fields = "id,text,username,timestamp,replies{id,username}"
        return self._request("GET", f"{media_id}/comments", fields=fields, limit=50).get("data", [])

    def reply(self, comment_id: str, message: str) -> str:
        return self._request("POST", f"{comment_id}/replies", message=message)["id"]


def refresh_long_lived_token(token: str) -> dict:
    """60일짜리 장기 토큰을 연장한다(발급 후 24시간 이상 지난 토큰만 가능)."""
    resp = requests.get(
        f"{BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"토큰 갱신 실패 {resp.status_code}: {resp.text[:300]}")
    return resp.json()
