"""최근 게시물의 새 댓글을 확인하고 AI 답글을 단다(또는 초안만 만든다).

사용법: python -m insta_auto.reply
이미 내가 답글을 단 댓글은 건너뛰므로 여러 번 실행해도 중복 답글이 생기지 않는다.
"""

import os
from datetime import datetime, timedelta, timezone

from . import ai
from .config import load_settings, require_env
from .instagram import InstagramClient


def _parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")


def _summary(lines: list[str]):
    """GitHub Actions 실행 화면의 'Summary'에 결과 표를 남긴다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    print(text)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")[:120]


def main():
    settings = load_settings()
    cfg = settings["reply"]
    mode = os.environ.get("REPLY_MODE", "").strip() or cfg["mode"]
    if not os.environ.get("IG_ACCESS_TOKEN", "").strip():
        return print("IG_ACCESS_TOKEN 없음 → 댓글 답글을 건너뜁니다.")
    client = InstagramClient(require_env("IG_ACCESS_TOKEN"), settings["instagram"]["api_version"])
    my_name = client.me()["username"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["max_age_days"])

    rows, handled = [], 0
    for media in client.recent_media(cfg["recent_posts"]):
        if not media.get("comments_count"):
            continue
        for c in client.comments(media["id"]):
            if handled >= cfg["max_replies_per_run"]:
                break
            if c.get("username") == my_name or _parse_ts(c["timestamp"]) < cutoff:
                continue
            replies = c.get("replies", {}).get("data", [])
            if any(r.get("username") == my_name for r in replies):
                continue  # 이미 답글 완료

            text = c.get("text", "")
            if any(k in text for k in cfg["manual_keywords"]):
                rows.append(f"| 직접 확인 | @{c['username']} | {_cell(text)} | 민감 키워드 |")
                continue

            result = ai.draft_reply(settings, media.get("caption", ""), text, c["username"])
            if result["action"] == "skip":
                continue
            if result["action"] == "manual":
                rows.append(f"| 직접 확인 | @{c['username']} | {_cell(text)} | {_cell(result['reason'])} |")
                continue

            handled += 1
            if mode == "auto":
                client.reply(c["id"], result["reply"])
                status = "등록"
            else:
                status = "초안"
            rows.append(f"| {status} | @{c['username']} | {_cell(text)} | {_cell(result['reply'])} |")

    header = [f"## 댓글 자동 답글 결과 (모드: {mode})", ""]
    if rows:
        _summary(header + ["| 상태 | 작성자 | 댓글 | 답글/사유 |", "|---|---|---|---|", *rows])
    else:
        _summary(header + ["새로 처리할 댓글이 없습니다."])


if __name__ == "__main__":
    main()
