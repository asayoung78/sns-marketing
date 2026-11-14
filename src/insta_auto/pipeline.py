"""초안 만들기 → 미리보기 → 게시까지의 공통 흐름."""

import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from . import ai, drafts, drive, gh, hosting, notify, reels, render
from .config import load_settings, require_env
from .generate import SOURCE_CREDIT, _caption, _hashtags, _short, _short_period
from .instagram import InstagramClient
from .sources import events

KST = ZoneInfo("Asia/Seoul")
UA = {"User-Agent": "Mozilla/5.0"}


def now() -> datetime:
    return datetime.now(KST)


def at(d: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=KST)


# ---------------- 행사 정보 저장·복원 ----------------
def ev_to_data(ev: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in ev.items()}


def ev_from_data(data: dict) -> dict:
    ev = dict(data)
    for k in ("start", "end"):
        ev[k] = date.fromisoformat(ev[k]) if ev.get(k) else None
    return ev


def facts_of(ev: dict) -> list[tuple[str, str]]:
    return [("기간", events.period_text(ev)), ("시간", _short(ev["time"], 120)), ("러닝타임", ev["runtime"]),
            ("장소", ev["venue"] or ev["address"]), ("관람료", _short(ev["price"], 140)), ("관람연령", ev["age"]),
            ("문의·예매", _short(ev["contact"], 80)), ("자세히", ev["url"])]


# ---------------- 내려받기 ----------------
def fetch(url: str, dest: Path) -> tuple[Path, str] | None:
    """주소에서 파일을 받아 (경로, 종류 image/video)를 돌려준다. 실패하면 None."""
    try:
        with requests.get(url, headers=UA, timeout=120, stream=True) as r:
            r.raise_for_status()
            kind = r.headers.get("content-type", "").split("/")[0]
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        if kind not in ("image", "video"):
            try:
                Image.open(dest).verify()
                kind = "image"
            except Exception:
                return None
        return dest, kind
    except Exception as e:
        print(f"내려받기 실패({url[:80]}): {e}")
        return None


# ---------------- 릴스 초안 ----------------
def make_reel_draft(settings: dict, slot_day: date, ev: dict, slot_plan: dict) -> dict:
    ev = events.with_detail(ev)
    period = events.period_text(ev)
    draft = ai.write_reel_draft(settings, ev, period)
    facts = facts_of(ev)
    caption = _caption(draft["caption"], [f"{k}: {v}" for k, v in facts],
                       f"※ 출처: {SOURCE_CREDIT.get(ev['source'], ev['source'])}. 일정·가격은 바뀔 수 있어요. 방문 전 공식 안내를 확인해 주세요.",
                       _hashtags(settings, draft["hashtags"]))
    post_at = at(slot_day, settings["schedule"]["reels_time"])
    label = {"공연": "공연"}.get(ev["category"], "축제")
    data = {"type": "reel", "slot": slot_day.isoformat(), "post_at": post_at.isoformat(), "label": label,
            "info": f"{_short_period(ev)} · {_short(ev['title'], 14)} · {_short(ev['venue'] or ev['address'], 12)}",
            "event": ev_to_data(ev)}
    title = f"[릴스 초안] {drafts.kdate(slot_day)} {settings['schedule']['reels_time']} · {ev['title']}"
    body = drafts.reel_body("{번호}", post_at, ev, facts, draft, caption, slot_plan) + drafts.pack(data)
    issue = gh.create_issue(title, body, [drafts.L_REEL])
    gh.update_issue(issue["number"], body=body.replace("{번호}", str(issue["number"])))
    preview(gh.get_issue(issue["number"]), notify_user=False)  # 첫 화면 미리보기 이미지 붙이기
    n = issue["number"]
    notify.send(
        f"🎬 <b>릴스 초안 #{n}</b> — {drafts.kdate(slot_day)} {settings['schedule']['reels_time']} 게시 예정\n"
        f"<b>{notify.esc(ev['title'])}</b> ({notify.esc(period)})\n\n"
        f"📹 영상: 드라이브 <code>{n}_행사명.mp4</code> 로 올려 주세요\n"
        f"✏️ 다듬고 댓글 <b>승인</b>: {gh.issue_url(n)}")
    return issue


# ---------------- 뉴스 초안 ----------------
def make_news_draft(settings: dict, post_day: date, recent_titles: list[str]) -> dict | None:
    post = ai.write_news_post(settings, f"{post_day} (게시일)", recent_titles)
    if not post["found"] or not post["sources"]:
        notify.send(f"📰 {drafts.kdate(post_day)} 부산 뉴스: 공식 출처로 확인된 소식을 찾지 못해 초안을 만들지 않았어요.")
        return None
    source = ", ".join(dict.fromkeys(s["name"] for s in post["sources"]))
    caption = _caption(post["caption"], [f"{s['name']}: {s['url']}" for s in post["sources"][:3]],
                       "※ 위 출처의 보도·발표 내용을 요약했어요.", _hashtags(settings, post["hashtags"]), "📰 출처")
    post_at = at(post_day, settings["schedule"]["news_time"])
    data = {"type": "news", "post_at": post_at.isoformat(), "source": source}
    title = f"[뉴스 초안] {drafts.kdate(post_day)} {settings['schedule']['news_time']} · {post['headline']}"
    body = drafts.news_body(post_at, post, caption, []) + drafts.pack(data)
    issue = gh.create_issue(title, body, [drafts.L_NEWS])
    preview(gh.get_issue(issue["number"]), notify_user=False)
    notify.send(f"📰 <b>뉴스 카드 초안 #{issue['number']}</b> — {drafts.kdate(post_day)} {settings['schedule']['news_time']} 게시 예정\n"
                f"<b>{notify.esc(post['headline'])}</b>\n✏️ 확인 후 댓글 <b>승인</b>: {gh.issue_url(issue['number'])}")
    return issue


# ---------------- 렌더링 ----------------
def news_pages(post: dict, source: str) -> list[dict]:
    pages = [{"type": "cover", "label": "뉴스", "title": post["headline1"], "headline1": post["headline1"],
              "headline2": post["headline2"], "info": _short(post["subtitle"], 30)}]
    pages += [{"type": "text", "number": i, "heading": s["heading"], "body": s["body"], "source": source}
              for i, s in enumerate(post["slides"][:3], start=1)]
    pages.append({"type": "closing", "title": post["closing"], "lines": [f"출처: {_short(source, 40)}", "부산온나우 팔로우하고 부산 소식 받아보기"]})
    return pages


def render_news(issue: dict, settings: dict, work: Path) -> list[Path]:
    data = drafts.unpack(issue["body"])
    post = drafts.news_from_body(issue["body"])
    source = ", ".join(s["name"] for s in post["sources"]) or data.get("source", "")
    return render.render_pages(news_pages(post, source), settings, work / "cards")


def reel_media(issue: dict, ev: dict, settings: dict, work: Path) -> dict:
    """영상(드라이브·댓글 첨부) 또는 사진 목록, 배경음악을 모은다."""
    texts = [issue["body"]] + [c["body"] for c in gh.trusted_comments(issue["number"])]
    video, photos = None, []
    found = drive.find_video(issue["number"])
    if found:
        video = drive.download(found, work / f"video{Path(found['name']).suffix or '.mp4'}")
    for i, url in enumerate(drafts.attachments(*texts)):
        got = fetch(url, work / f"att{i}")
        if not got:
            continue
        path, kind = got
        if kind == "video" and not video:
            video = path
        elif kind == "image":
            photos.append(path)
    if not video:
        for i, url in enumerate(ev.get("images", [])):
            got = fetch(url, work / f"official{i}")
            if got and got[1] == "image":
                photos.append(got[0])
    music = None
    tracks = drive.music_tracks()
    if tracks:
        music = drive.download(tracks[issue["number"] % len(tracks)], work / "music.mp3")
    return {"video": video, "images": photos[: settings["reels"]["max_slides"]], "music": music,
            "user_media": bool(found) or bool(drafts.attachments(*texts))}


def render_reel_issue(issue: dict, settings: dict, work: Path) -> tuple[Path, Path, dict]:
    data = drafts.unpack(issue["body"])
    ev = ev_from_data(data["event"])
    edit = drafts.reel_from_body(issue["body"])
    media = reel_media(issue, ev, settings, work)
    mp4, cover = reels.render_reel(work / "reel", label=data["label"], headline1=edit["headline1"],
                                   headline2=edit["headline2"], info=data["info"], subtitles=edit["subtitles"],
                                   settings=settings, video=media["video"], images=media["images"], music=media["music"])
    return mp4, cover, media


# ---------------- 미리보기 ----------------
def preview(issue: dict, notify_user: bool = True):
    """현재 초안 내용으로 다시 만들어 미리보기 주소를 초안에 남긴다(AI 비용 없음)."""
    settings = load_settings()
    data = drafts.unpack(issue["body"])
    n = issue["number"]
    stamp = now().strftime("%Y%m%d-%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if data["type"] == "news":
            cards = render_news(issue, settings, work)
            urls = hosting.public_urls(cards, settings["hosting"]["method"], f"{stamp}-news-{n}")
            imgs = " ".join(f'<img src="{u}" width="180">' for u in urls)
            gh.comment(n, f"🖼️ **카드 미리보기** ({len(urls)}장)\n\n{imgs}")
        else:
            mp4, cover, media = render_reel_issue(issue, settings, work)
            urls = hosting.public_urls([mp4, cover], settings["hosting"]["method"], f"{stamp}-reel-{n}")
            how = "직접 올린 영상" if media["video"] else f"사진 슬라이드 {len(media['images'])}장"
            gh.comment(n, f"🎬 **릴스 미리보기** ({how}, 음악 {'있음' if media['music'] else '없음'})\n\n"
                          f'<img src="{urls[1]}" width="220">\n\n▶️ [영상 보기]({urls[0]})')
    if notify_user:
        notify.send(f"🔎 #{n} 미리보기 준비됐어요: {gh.issue_url(n)}")


# ---------------- 게시 ----------------
def publish(issue: dict):
    settings = load_settings()
    data = drafts.unpack(issue["body"])
    n = issue["number"]
    client = InstagramClient(require_env("IG_ACCESS_TOKEN"), settings["instagram"]["api_version"])
    stamp = now().strftime("%Y%m%d-%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if data["type"] == "news":
            post = drafts.news_from_body(issue["body"])
            cards = render_news(issue, settings, work)
            urls = hosting.public_urls(cards, settings["hosting"]["method"], f"{stamp}-news-{n}")
            media_id = client.publish_carousel(urls, post["caption"])
        else:
            edit = drafts.reel_from_body(issue["body"])
            mp4, cover, _ = render_reel_issue(issue, settings, work)
            urls = hosting.public_urls([mp4, cover], settings["hosting"]["method"], f"{stamp}-reel-{n}")
            media_id = client.publish_reel(urls[0], edit["caption"], cover_url=urls[1])
    gh.comment(n, f"✅ 인스타그램에 게시했어요. (media_id: {media_id})")
    gh.add_labels(n, [drafts.L_DONE])
    gh.update_issue(n, state="closed")
    notify.send(f"✅ #{n} 게시 완료! {notify.esc(issue['title'])}")
    return media_id


def fail(issue: dict, err: Exception):
    n = issue["number"]
    gh.add_labels(n, [drafts.L_ERR])
    gh.comment(n, f"⚠️ 처리 중 오류가 났어요.\n\n```\n{str(err)[:1500]}\n```")
    notify.send(f"⚠️ #{n} 처리 오류: {notify.esc(str(err)[:300])}\n{gh.issue_url(n)}")
