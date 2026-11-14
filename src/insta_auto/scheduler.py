"""15분마다 실행되어 '지금 할 일'을 처리한다. 같은 일을 두 번 하지 않도록 GitHub 초안 상태로 확인한다.

할 일: 주간 기획표 · 릴스 초안(게시 3일 전) · 뉴스 초안(전날 밤) · 당일 안내 · 승인된 초안 게시
사용법: python -m insta_auto.scheduler [--task all|plan|reel_drafts|news_drafts|reminders|publish] [--force]
"""

import argparse
import os
from datetime import date, datetime, timedelta

from . import ai, drafts, drive, gh, notify, pipeline
from .config import load_settings
from .pipeline import at, now
from .sources import events

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MARK_REMIND = "<!-- reminder-sent -->"
MARK_MISSED = "<!-- missed-sent -->"


def slot_days(settings: dict, start: date, end: date) -> list[date]:
    sch = settings["schedule"]
    anchor, step = date.fromisoformat(sch["reels_anchor"]), sch["reels_interval_days"]
    first = anchor if start <= anchor else anchor + timedelta(days=-(-(start - anchor).days // step) * step)
    days, d = [], first
    while d <= end:
        days.append(d)
        d += timedelta(days=step)
    return days


def all_drafts(label: str) -> list[dict]:
    return gh.list_issues(label, state="all")


def _ev_line(ev: dict) -> str:
    return f"{ev['title']} ({ev['category']}·{ev['genre'] or '-'}, {ev['venue'] or ev['address']}, {events.period_text(ev)})"


# ---------------- 주간 기획표 ----------------
def task_plan(settings: dict, force: bool = False):
    sch, t = settings["schedule"], now()
    today = t.date()
    if not force and (WEEKDAYS[today.weekday()] != sch["plan_day"] or t < at(today, sch["plan_time"])):
        return
    week = today.isoformat()
    if any(drafts.unpack(i["body"]).get("week") == week for i in all_drafts(drafts.L_PLAN)):
        return
    reel_issues = all_drafts(drafts.L_REEL)
    taken = {drafts.unpack(i["body"]).get("slot") for i in reel_issues}
    days = [d for d in slot_days(settings, today + timedelta(days=1), today + timedelta(days=sch["plan_horizon_days"]))
            if d.isoformat() not in taken]
    if not days:
        return
    posted = {drafts.unpack(i["body"]).get("event", {}).get("id") for i in reel_issues}
    cands = events.candidates(settings, today, posted)
    if not cands:
        notify.send("📅 이번 주 릴스 기획표: 소개할 부산 행사를 찾지 못했어요. data/manual_events.csv에 직접 추가할 수 있어요.")
        return
    by_id = {c["id"]: c for c in cands}
    recent = [i["title"] for i in reel_issues[:15]]
    slots = []
    for s in ai.plan_slots(settings, [d.isoformat() for d in days], cands, recent):
        main = by_id.get(s["main_id"])
        if not main:
            continue
        slots.append({**s, "main": pipeline.ev_to_data(main),
                      "backup": pipeline.ev_to_data(by_id[s["backup_id"]]) if s["backup_id"] in by_id else None})
    lines = [f"> 📅 다음 {sch['plan_horizon_days']}일 릴스 기획표예요. 게시 {sch['reels_draft_days_before']}일 전에 행사별 초안이 따로 만들어져요.",
             "> 초안에서 댓글 `교체`를 남기면 대체 후보로 다시 만들어요(AI 비용 발생).\n"]
    tg = [f"📅 <b>릴스 기획표</b> ({drafts.kdate(today)} 기준)"]
    for s in slots:
        d = date.fromisoformat(s["date"])
        main = pipeline.ev_from_data(s["main"])
        lines += [f"### {drafts.kdate(d)} {sch['reels_time']} — {main['title']}",
                  f"- {_ev_line(main)}", f"- 추천 이유: {s['reason']}", f"- 🎥 촬영 추천: {s['shoot_when']}",
                  *[f"  - {shot}" for shot in s["shots"]],
                  f"- 대체 후보: {pipeline.ev_from_data(s['backup'])['title'] if s['backup'] else '(없음)'}\n"]
        tg.append(f"• {drafts.kdate(d)} <b>{notify.esc(main['title'])}</b>\n   🎥 {notify.esc(s['shoot_when'])}")
    issue = gh.create_issue(f"[기획표] {drafts.kdate(today)} 주간 릴스 일정", "\n".join(lines) + drafts.pack(
        {"type": "plan", "week": week, "slots": slots}), [drafts.L_PLAN])
    tg.append(f"\n자세히(촬영 장면 포함): {gh.issue_url(issue['number'])}")
    notify.send("\n".join(tg))


def plan_entry(slot: str) -> dict | None:
    for issue in all_drafts(drafts.L_PLAN):  # 최신 기획표부터
        for s in drafts.unpack(issue["body"]).get("slots", []):
            if s["date"] == slot:
                return s
    return None


# ---------------- 릴스 초안 ----------------
def task_reel_drafts(settings: dict):
    sch, t = settings["schedule"], now()
    today = t.date()
    reel_issues = all_drafts(drafts.L_REEL)
    taken = {drafts.unpack(i["body"]).get("slot") for i in reel_issues}
    for d in slot_days(settings, today, today + timedelta(days=sch["reels_draft_days_before"])):
        if d.isoformat() in taken or at(d, sch["reels_time"]) <= t:
            continue
        posted = {drafts.unpack(i["body"]).get("event", {}).get("id") for i in reel_issues
                  if drafts.L_SKIP not in {l["name"] for l in i["labels"]}}
        entry = plan_entry(d.isoformat())
        if entry and entry["main"]["id"] in posted:  # 이미 다른 날 소개한 행사면 대체 후보로
            entry = {**entry, "main": entry["backup"]} if entry.get("backup") and entry["backup"]["id"] not in posted else None
        if not entry:  # 기획표가 없거나 후보가 겹치면 이 날짜만 바로 고른다
            cands = events.candidates(settings, today, posted)
            cands = [c for c in cands if c["end"] >= d]
            if not cands:
                notify.send(f"🎬 {drafts.kdate(d)} 릴스: 소개할 행사를 찾지 못해 초안을 만들지 않았어요.")
                continue
            picked = ai.plan_slots(settings, [d.isoformat()], cands, [i["title"] for i in reel_issues[:15]])[0]
            by_id = {c["id"]: c for c in cands}
            entry = {**picked, "main": pipeline.ev_to_data(by_id.get(picked["main_id"], cands[0]))}
        pipeline.make_reel_draft(settings, d, pipeline.ev_from_data(entry["main"]), entry)


# ---------------- 뉴스 초안 ----------------
def task_news_drafts(settings: dict):
    sch, t = settings["schedule"], now()
    issues = all_drafts(drafts.L_NEWS)
    done = {drafts.unpack(i["body"]).get("post_at", "")[:10] for i in issues}
    for d in (t.date(), t.date() + timedelta(days=1)):
        if WEEKDAYS[d.weekday()] not in sch["news_days"] or d.isoformat() in done:
            continue
        if at(d - timedelta(days=1), sch["news_draft_time"]) <= t < at(d, sch["news_time"]):
            pipeline.make_news_draft(settings, d, [i["title"] for i in issues[:15]])


# ---------------- 당일 안내 ----------------
def task_reminders(settings: dict):
    sch, t = settings["schedule"], now()
    for issue in gh.list_issues(drafts.L_REEL):
        data = drafts.unpack(issue["body"])
        if data.get("slot") != t.date().isoformat() or t < at(t.date(), sch["reels_reminder_time"]):
            continue
        cmts = gh.comments(issue["number"])
        if any(MARK_REMIND in c["body"] for c in cmts):
            continue
        n = issue["number"]
        has_video = drive.find_video(n) is not None
        has_photos = bool(drafts.attachments(issue["body"], *[c["body"] for c in cmts
                                                              if c.get("author_association") in gh.TRUSTED]))
        approved = any(l["name"] == drafts.L_OK for l in issue["labels"])
        msg = [f"⏰ 오늘 {sch['reels_time']} 릴스 #{n}"]
        if not has_video:
            msg.append("📹 드라이브에 영상이 없어서 " + ("올려 주신 사진과 " if has_photos else "") + "공식 사진으로 사진 슬라이드 릴스를 만들게요.")
        if not approved:
            msg.append("✋ 아직 승인 전이에요. 승인해야 게시돼요.")
        if len(msg) > 1:
            notify.send("\n".join(msg) + f"\n{gh.issue_url(n)}")
        gh.comment(n, f"{MARK_REMIND}\n⏰ 당일 안내를 보냈어요.")


# ---------------- 게시 ----------------
def task_publish(settings: dict):
    t = now()
    for label in (drafts.L_REEL, drafts.L_NEWS):
        for issue in gh.list_issues(label):
            names = {l["name"] for l in issue["labels"]}
            data = drafts.unpack(issue["body"])
            if not data.get("post_at") or datetime.fromisoformat(data["post_at"]) > t or drafts.L_DONE in names:
                continue
            if drafts.L_OK in names and drafts.L_ERR not in names:
                if not os.environ.get("IG_ACCESS_TOKEN", "").strip():
                    if not any(MARK_MISSED in c["body"] for c in gh.comments(issue["number"])):
                        gh.comment(issue["number"], f"{MARK_MISSED}\n⏸️ 인스타그램 토큰(IG_ACCESS_TOKEN)이 아직 없어 게시를 보류했어요. 등록 후 `지금 게시`를 남겨 주세요.")
                        notify.send(f"⏸️ #{issue['number']} 인스타 토큰이 없어 게시 보류")
                    continue
                try:
                    pipeline.publish(issue)
                except Exception as e:
                    pipeline.fail(issue, e)
            elif drafts.L_OK not in names and not any(MARK_MISSED in c["body"] for c in gh.comments(issue["number"])):
                gh.comment(issue["number"], f"{MARK_MISSED}\n⏸️ 게시 시간이 지났지만 승인되지 않아 올리지 않았어요. 지금 올리려면 `지금 게시` 댓글을 남겨 주세요.")
                notify.send(f"⏸️ #{issue['number']} 승인되지 않아 게시하지 않았어요.\n{gh.issue_url(issue['number'])}")


TASKS = {"plan": task_plan, "reel_drafts": task_reel_drafts, "news_drafts": task_news_drafts,
         "reminders": task_reminders, "publish": task_publish}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="all", choices=["all", *TASKS])
    parser.add_argument("--force", action="store_true", help="기획표를 요일·시간과 상관없이 지금 만들기")
    args = parser.parse_args()
    settings = load_settings()
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not settings["schedule"].get("enabled"):
        return print("settings.toml의 [schedule] enabled = false → 예약 실행을 건너뜁니다.")
    gh.ensure_labels(drafts.LABELS)
    print(f"실행 시각(한국): {now():%Y-%m-%d %H:%M}")
    for name, fn in TASKS.items():
        if args.task not in ("all", name):
            continue
        try:
            fn(settings, args.force) if name == "plan" else fn(settings)
        except Exception as e:  # 한 작업이 실패해도 나머지는 진행
            print(f"[{name}] 실패: {e}")
            notify.send(f"⚠️ 자동화 작업 '{name}' 실패: {notify.esc(str(e)[:300])}")


if __name__ == "__main__":
    main()
