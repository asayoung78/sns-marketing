"""2단계: generate가 만든 카드뉴스를 Instagram에 캐러셀로 게시한다.

사용법: python -m insta_auto.publish
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import HISTORY_PATH, ROOT, load_settings, require_env
from .hosting import public_urls
from .instagram import InstagramClient


def main():
    settings = load_settings()
    pending_path = ROOT / "data" / "pending.json"
    if not pending_path.exists():
        raise SystemExit("게시할 콘텐츠가 없습니다. 먼저 generate를 실행하세요.")
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    post_dir = ROOT / pending["dir"]
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))

    urls = public_urls([post_dir / name for name in pending["images"]], settings["hosting"]["method"])
    client = InstagramClient(require_env("IG_ACCESS_TOKEN"), settings["instagram"]["api_version"])
    media_id = client.publish_carousel(urls, post["full_caption"])

    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    history.append({
        "posted_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="minutes"),
        "title": post["cover_title"],
        "topic": post["topic"],
        "media_id": media_id,
        "dir": pending["dir"],
    })
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    pending_path.unlink()
    print(f"게시 완료: {post['cover_title']} (media_id={media_id})")


if __name__ == "__main__":
    main()
