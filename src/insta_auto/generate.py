"""1단계: AI로 원고를 쓰고 카드뉴스 이미지를 만든다.

사용법: python -m insta_auto.generate [--topic "주제"]
결과: media/<날짜시각>/ 아래에 01.jpg… 와 post.json, 그리고 data/pending.json
"""

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ai, render
from .config import HISTORY_PATH, MEDIA_DIR, ROOT, load_settings

KST = ZoneInfo("Asia/Seoul")


def build_caption(post: dict, settings: dict) -> str:
    content = settings["content"]
    tags = list(content["fixed_hashtags"])
    for tag in post["hashtags"]:
        tag = "#" + tag.lstrip("#").replace(" ", "")
        if tag not in tags:
            tags.append(tag)
    return f"{post['caption'].strip()}\n\n{' '.join(tags[: content['max_hashtags']])}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="", help="이번 게시물 주제를 직접 지정 (비우면 AI가 선택)")
    args = parser.parse_args()

    settings = load_settings()
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    recent_titles = [h["title"] for h in history[-20:]]
    now = datetime.now(KST)

    post = ai.generate_post(settings, recent_titles, now.strftime("%Y-%m-%d (%A)"), args.topic.strip() or None)
    post["full_caption"] = build_caption(post, settings)

    out_dir = MEDIA_DIR / now.strftime("%Y%m%d-%H%M")
    paths = render.render_cards(post, settings, out_dir)
    (out_dir / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    pending = {"dir": out_dir.relative_to(ROOT).as_posix(), "images": [p.name for p in paths]}
    (ROOT / "data" / "pending.json").write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"생성 완료: {post['cover_title']} ({len(paths)}장) → {pending['dir']}")
    print(post["full_caption"])


if __name__ == "__main__":
    main()
