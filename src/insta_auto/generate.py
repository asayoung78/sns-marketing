"""1단계: 오늘 게시물 원고를 만들고 카드뉴스 이미지를 만든다.

사용법: python -m insta_auto.generate [--kind event|exhibit|news] [--topic "행사명/주제"]
결과: media/<날짜시각>/ 아래에 01.jpg… 와 post.json, 그리고 data/pending.json
"""

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ai, render
from .config import HISTORY_PATH, MEDIA_DIR, ROOT, load_settings
from .sources import events

KST = ZoneInfo("Asia/Seoul")
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
CAPTION_LIMIT = 2200  # Instagram 본문 최대 글자 수


def _short(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _hashtags(settings: dict, extra: list[str]) -> str:
    content = settings["content"]
    tags = list(content["fixed_hashtags"])
    for tag in extra:
        tag = "#" + tag.lstrip("#").replace(" ", "")
        if tag not in tags:
            tags.append(tag)
    return " ".join(tags[: content["max_hashtags"]])


def _caption(body: str, info_lines: list[str], notice: str, tags: str, heading: str = "📍 정보") -> str:
    info = "\n".join(f"· {line}" for line in info_lines if line.split(":", 1)[-1].strip())
    parts = [body.strip(), info and f"{heading}\n{info}", notice, tags]
    text = "\n\n".join(p for p in parts if p)
    if len(text) > CAPTION_LIMIT:  # 넘치면 본문을 줄인다
        over = len(text) - CAPTION_LIMIT + 1
        text = text.replace(body.strip(), _short(body, max(100, len(body) - over)), 1)
    return text


def _closing(settings: dict, title: str, extra: list[str] = ()) -> dict:
    return {"type": "closing", "title": title,
            "lines": [*extra, "저장해 두고 친구랑 같이 가보자!", f"{settings['account']['brand']} 팔로우하고 부산 소식 받아보기"]}


# ---------------- 종류별 원고 ----------------
def build_event(settings, today, history, topic):
    posted = {h.get("key") for h in history}
    cands = events.candidates(settings, today, posted)
    if topic:
        cands = [c for c in cands if topic in c["title"]] or cands
    if not cands:
        return None
    recent = [h["title"] for h in history]
    chosen_id = cands[0]["id"] if topic else ai.pick_event(settings, cands, recent, str(today))
    ev = events.with_detail(next((c for c in cands if c["id"] == chosen_id), cands[0]))
    period = events.period_text(ev)
    post = ai.write_event_post(settings, ev, period)
    venue = ev["venue"] or ev["address"]
    rows = [("기간", period), ("장소", _short(venue, 60)), ("시간", _short(ev["time"], 120)),
            ("관람료", _short(ev["price"], 120)), ("관람연령", _short(ev["age"], 40)), ("문의·예매", _short(ev["contact"], 80))]
    pages = [
        {"type": "cover", "label": ev["category"], "subtitle": post["hook"], "title": ev["title"],
         "meta": [f"기간  {period}", f"장소  {_short(venue, 40)}"]},
        {"type": "text", "heading": "이런 행사예요", "body": post["intro"]},
        {"type": "list", "heading": "이래서 추천해요", "items": post["points"][:3]},
        {"type": "info", "heading": "행사 정보", "rows": rows, "source": ev["source"]},
        _closing(settings, "이번에 같이 가볼래?", ["방문 전 공식 안내를 꼭 확인해 주세요"]),
    ]
    caption = _caption(post["caption"], [f"{k}: {v}" for k, v in rows] + [f"자세히: {ev['url']}" if ev["url"] else ""],
                       f"※ {ev['source']} 공개 정보 기준이며 일정·가격은 바뀔 수 있어요. 방문 전 공식 안내를 확인해 주세요.",
                       _hashtags(settings, post["hashtags"]))
    return {"kind": "event", "key": ev["id"], "title": ev["title"], "pages": pages, "caption": caption, "raw": post}


def build_exhibit(settings, today, history, topic):
    recent = [h["title"] for h in history if h.get("kind") == "exhibit"]
    post = ai.write_exhibit_post(settings, f"{today} {topic}".strip(), recent)
    if not post["found"] or not post["period"] or not post["venue"]:
        print("전시 정보를 공식 출처로 확인하지 못함 → 다른 종류로 대체")
        return None
    rows = [("기간", post["period"]), ("장소", post["venue"]), ("관람시간", post["time"]),
            ("관람료", post["price"]), ("휴관일", post["closed"])]
    pages = [
        {"type": "cover", "label": "전시", "subtitle": post["hook"], "title": post["title"],
         "meta": [f"기간  {post['period']}", f"장소  {_short(post['venue'], 40)}"]},
        {"type": "text", "heading": "어떤 전시냐면", "body": post["intro"]},
        {"type": "list", "heading": "관람 포인트", "items": post["points"][:3]},
        {"type": "info", "heading": "관람 정보", "rows": [(k, _short(v, 100)) for k, v in rows], "source": post["source_name"]},
        _closing(settings, "주말 전시 나들이 어떻노?", ["방문 전 공식 홈페이지를 꼭 확인해 주세요"]),
    ]
    caption = _caption(post["caption"], [f"{k}: {v}" for k, v in rows] + [f"자세히: {post['source_url']}"],
                       f"※ {post['source_name']} 공개 정보 기준이며 바뀔 수 있어요.", _hashtags(settings, post["hashtags"]))
    return {"kind": "exhibit", "key": f"exhibit:{post['title']}", "title": post["title"], "pages": pages, "caption": caption, "raw": post}


def build_news(settings, today, history, topic):
    recent = [h["title"] for h in history if h.get("kind") == "news"]
    post = ai.write_news_post(settings, f"{today} {topic}".strip(), recent)
    if not post["found"] or not post["sources"]:
        print("확인된 부산 뉴스가 없음 → 다른 종류로 대체")
        return None
    source = ", ".join(dict.fromkeys(s["name"] for s in post["sources"]))
    pages = [{"type": "cover", "label": "부산 뉴스", "title": post["headline"], "meta": [post["subtitle"]]}]
    pages += [{"type": "text", "number": i, "heading": s["heading"], "body": s["body"], "source": source}
              for i, s in enumerate(post["slides"][:3], start=1)]
    pages.append({"type": "closing", "title": post["closing"],
                  "lines": [f"출처: {_short(source, 40)}", f"{settings['account']['brand']} 팔로우하고 부산 소식 받아보기"]})
    caption = _caption(post["caption"], [f"{s['name']}: {s['url']}" for s in post["sources"][:3]],
                       "※ 위 출처의 보도·발표 내용을 요약했어요.", _hashtags(settings, post["hashtags"]), "📰 출처")
    return {"kind": "news", "key": f"news:{post['headline']}", "title": post["headline"], "pages": pages, "caption": caption, "raw": post}


BUILDERS = {"event": build_event, "exhibit": build_exhibit, "news": build_news}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", default="", choices=["", *BUILDERS], help="비우면 settings.toml 요일표를 따름")
    parser.add_argument("--topic", default="", help="행사명이나 주제를 직접 지정 (선택)")
    args = parser.parse_args()

    settings = load_settings()
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    now = datetime.now(KST)
    kind = args.kind or settings["schedule"][WEEKDAYS[now.weekday()]]

    # 오늘 종류가 실패하면 나머지 종류로 차례로 대체
    order = [kind] + [k for k in ("event", "exhibit", "news") if k != kind]
    result = None
    for k in order:
        result = BUILDERS[k](settings, now.date(), history, args.topic.strip())
        if result:
            break
    if not result:
        raise SystemExit("오늘 올릴 콘텐츠를 만들지 못했습니다. API 키와 실행 기록을 확인하세요.")

    out_dir = MEDIA_DIR / now.strftime("%Y%m%d-%H%M%S")
    paths = render.render_pages(result["pages"], settings, out_dir)
    post = {k: result[k] for k in ("kind", "key", "title", "raw")} | {"full_caption": result["caption"]}
    (out_dir / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    pending = {"dir": out_dir.relative_to(ROOT).as_posix(), "images": [p.name for p in paths]}
    (ROOT / "data" / "pending.json").write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"생성 완료 [{result['kind']}] {result['title']} ({len(paths)}장) → {pending['dir']}\n")
    print(result["caption"])


if __name__ == "__main__":
    main()
