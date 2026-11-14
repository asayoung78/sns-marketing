"""초안(이슈)에 남긴 댓글 명령을 처리한다: 승인 · 승인 취소 · 미리보기 · 건너뛰기 · 지금 게시 · 교체

공개 저장소라 저장소 주인(OWNER)·협업자의 댓글만 명령으로 인정한다.
"""

import json
import os
from datetime import date, datetime

from . import ai, drafts, gh, notify, pipeline
from .config import load_settings
from .sources import events

COMMANDS = ("승인 취소", "승인", "미리보기", "건너뛰기", "지금 게시", "교체")


def parse(body: str) -> str:
    first = (body or "").strip().splitlines()[0].strip() if (body or "").strip() else ""
    first = first.strip("`*!. ")
    return next((c for c in COMMANDS if first == c), "")


def replace_draft(issue: dict):
    """같은 날짜로 대체 후보(없으면 새 후보)를 골라 초안을 다시 만든다."""
    settings = load_settings()
    data = drafts.unpack(issue["body"])
    slot = date.fromisoformat(data["slot"])
    from .scheduler import plan_entry  # 순환 참조 방지
    entry = plan_entry(data["slot"]) or {}
    backup = entry.get("backup")
    if backup and backup.get("id") != data["event"]["id"]:
        new = {**entry, "main": backup}
    else:
        used = {drafts.unpack(i["body"]).get("event", {}).get("id") for i in gh.list_issues(drafts.L_REEL, "all")}
        cands = [c for c in events.candidates(settings, pipeline.now().date(), used) if c["end"] >= slot]
        if not cands:
            raise RuntimeError("바꿀 수 있는 다른 행사가 없어요.")
        picked = ai.plan_slots(settings, [data["slot"]], cands, [])[0]
        by_id = {c["id"]: c for c in cands}
        new = {**picked, "main": pipeline.ev_to_data(by_id.get(picked["main_id"], cands[0]))}
    gh.add_labels(issue["number"], [drafts.L_SKIP])
    gh.update_issue(issue["number"], state="closed")
    created = pipeline.make_reel_draft(settings, slot, pipeline.ev_from_data(new["main"]), new)
    gh.comment(issue["number"], f"🔁 다른 행사로 바꿨어요 → #{created['number']}")


def main():
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    cmt, issue = event["comment"], event["issue"]
    if cmt.get("author_association") not in gh.TRUSTED:
        return print("저장소 주인·협업자의 댓글이 아니라 무시합니다.")
    labels = {l["name"] for l in issue["labels"]}
    if not labels & {drafts.L_REEL, drafts.L_NEWS}:
        return print("초안이 아닌 글이라 무시합니다.")
    command = parse(cmt["body"])
    if not command:
        return print("명령이 없는 댓글입니다(사진 첨부 등).")
    n = issue["number"]
    issue = gh.get_issue(n)  # 최신 본문
    data = drafts.unpack(issue["body"])
    when = datetime.fromisoformat(data["post_at"]) if data.get("post_at") else None
    try:
        if command == "승인":
            gh.remove_label(n, drafts.L_ERR)
            gh.add_labels(n, [drafts.L_OK])
            gh.comment(n, f"✅ 승인됐어요. **{drafts.kdate(when.date())} {when:%H:%M}** 에 게시할게요. "
                          "그 전까지 글을 더 고쳐도 마지막 내용으로 올라가요.")
            notify.send(f"✅ #{n} 승인 — {drafts.kdate(when.date())} {when:%H:%M} 게시 예정")
        elif command == "승인 취소":
            gh.remove_label(n, drafts.L_OK)
            gh.comment(n, "↩️ 승인을 취소했어요. 다시 `승인`하기 전까지 게시하지 않아요.")
        elif command == "미리보기":
            gh.comment(n, "⏳ 미리보기를 만드는 중이에요(1~3분).")
            pipeline.preview(issue)
        elif command == "건너뛰기":
            gh.add_labels(n, [drafts.L_SKIP])
            gh.update_issue(n, state="closed")
            gh.comment(n, "⏭️ 이 초안은 게시하지 않고 닫았어요.")
        elif command == "지금 게시":
            gh.comment(n, "⏳ 지금 게시하는 중이에요.")
            pipeline.publish(issue)
        elif command == "교체":
            if data.get("type") != "reel":
                return gh.comment(n, "`교체`는 릴스 초안에서만 쓸 수 있어요.")
            gh.comment(n, "⏳ 다른 행사로 새 초안을 만드는 중이에요(AI 비용 발생, 2~4분).")
            replace_draft(issue)
    except Exception as e:
        pipeline.fail(issue, e)
        raise


if __name__ == "__main__":
    main()
