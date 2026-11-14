"""초안(GitHub 이슈) 본문을 만들고, 사용자가 고친 본문을 다시 읽는다.

본문은 '## 제목' 단위로 나뉘며, 사용자는 각 칸의 글을 자유롭게 고칠 수 있다.
맨 아래 숨은 줄(<!-- busan-onnow-data:... -->)에 행사 원본 정보가 들어 있어 수정하면 안 된다.
"""

import base64
import json
import re
from datetime import date, datetime

DATA_RE = re.compile(r"<!-- busan-onnow-data:([A-Za-z0-9+/=]+) -->")
DAYS = "월화수목금토일"

# 라벨 이름과 색
L_PLAN, L_REEL, L_NEWS = "기획표", "릴스초안", "뉴스초안"
L_OK, L_DONE, L_SKIP, L_ERR = "승인됨", "게시완료", "건너뜀", "오류"
LABELS = {L_PLAN: "6f42c1", L_REEL: "e36209", L_NEWS: "0366d6", L_OK: "28a745",
          L_DONE: "6a737d", L_SKIP: "d1d5da", L_ERR: "d73a49"}


def kdate(d: date) -> str:
    return f"{d.month}/{d.day}({DAYS[d.weekday()]})"


def pack(data: dict) -> str:
    raw = base64.b64encode(json.dumps(data, ensure_ascii=False, default=str).encode()).decode()
    return f"\n\n---\n_⚠️ 아래 숨은 줄은 자동화용이라 지우거나 고치면 안 돼요._\n<!-- busan-onnow-data:{raw} -->"


def unpack(body: str) -> dict:
    m = DATA_RE.search(body or "")
    return json.loads(base64.b64decode(m.group(1))) if m else {}


def sections(body: str) -> dict[str, str]:
    """'## 제목' 아래 글을 {제목: 글}로. 안내용 줄(> 또는 _로 시작)은 뺀다."""
    out, current = {}, None
    for line in (body or "").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None and not DATA_RE.search(line):
            out[current].append(line)
    return {k: "\n".join(v).split("\n---\n_⚠️")[0].strip() for k, v in out.items()}


def lines_of(text: str) -> list[str]:
    """목록 칸을 한 줄씩. '- ', '1. ' 같은 머리표와 괄호 안내 줄은 뺀다."""
    result = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("(", ">", "_", "<!--")):
            continue
        result.append(re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line))
    return result


def section_starting(secs: dict, prefix: str) -> str:
    return next((v for k, v in secs.items() if k.startswith(prefix)), "")


def header(post_at: datetime, kind: str) -> str:
    when = f"{kdate(post_at.date())} {post_at:%H:%M}"
    media = " · 사진은 이 글 아래 **댓글에 첨부**" if kind == "reel" else ""
    return (f"> 📌 **게시 예정: {when}** — 내용을 고친 뒤 댓글로 **`승인`** 을 남기면 그 시간에 올라가요.\n"
            f"> 댓글 명령: `미리보기`(지금 내용으로 다시 만들어 보기, AI 비용 없음) · `승인` · `승인 취소` · `건너뛰기` · `지금 게시`{media}\n")


# ---------------- 릴스 초안 ----------------
def reel_body(number_hint: str, post_at: datetime, ev: dict, facts: list[tuple[str, str]], draft: dict,
              caption: str, plan_slot: dict, preview_url: str = "") -> str:
    tips = draft["tips"]
    tip_names = {"transport": "교통", "parking": "주차", "nearby": "근처 맛집·카페", "photo_spot": "포토존",
                 "crowd": "붐비는 시간", "weather": "비 올 때"}
    tip_lines = [f"- {tip_names[k]}: {v or '**확인 필요**'}" for k, v in tips.items()]
    parts = [
        header(post_at, "reel"),
        f"![첫 화면 미리보기]({preview_url})\n" if preview_url else "",
        "## 큰 제목\n(첫 화면 두 줄 제목. 둘째 줄은 강조색으로 나와요. 각 7자 안팎)",
        f"{draft['headline1']}\n{draft['headline2']}\n",
        "## 자막\n(한 줄에 하나씩, 위에서부터 차례로 나와요. 고치거나 줄을 더하고 빼도 돼요. 한 줄 18자 안팎)",
        "\n".join(f"- {s}" for s in draft["subtitles"]) + "\n",
        "## 인스타 본문\n" + caption + "\n",
        "## 영상·사진 올리기",
        f"- 🎬 **영상**: 구글 드라이브 `부산온나우_영상` 폴더에 이름 앞에 **`{number_hint}_`** 를 붙여 올려 주세요. (예: `{number_hint}_{re.sub(r'[^가-힣A-Za-z0-9]', '', ev['title'])[:10]}.mp4`)",
        "- 📷 **사진**: 이 글 아래 댓글에 사진을 첨부하면 슬라이드 맨 앞에 들어가요.",
        "- 영상이 없으면 공식 포스터·사진(+ 올린 사진)으로 **사진 슬라이드 릴스**를 만들어요.\n",
        "## 촬영 가이드",
        f"- 촬영 추천: {plan_slot.get('shoot_when') or '행사 기간 중'}",
        *[f"- {s}" for s in plan_slot.get("shots", [])],
        "- 세로로, 한 장면 3~5초, 관객 얼굴은 작게 나오게\n",
        "## 조사 자료 (참고용 · 게시물에 바로 쓰이지 않아요)",
        f"**꼭 봐야 하는 이유**: {draft['one_liner'] or '**확인 필요**'}",
        "**관람 포인트**", *([f"- {h}" for h in draft["highlights"]] or ["- **확인 필요**"]),
        f"**출연진 화제성**: {draft['cast_buzz'] or '**확인 필요**'}",
        "**관객 후기**", *([f"- {r}" for r in draft["reviews"]] or ["- **확인 필요**"]),
        "**현장 꿀팁**", *tip_lines,
        "**⚠️ 확인이 필요한 항목**", *([f"- [ ] {n}" for n in draft["needs_check"]] or ["- (없음)"]),
        "**출처**", *([f"- [{s['name']}]({s['url']})" for s in draft["sources"]] or ["- (없음)"]),
        "",
        "## 기본 정보 (공공데이터 · 고치지 마세요)",
        *[f"- {k}: {v}" for k, v in facts if v],
    ]
    return "\n".join(p for p in parts if p is not None)


# ---------------- 뉴스 초안 ----------------
def news_body(post_at: datetime, post: dict, caption: str, preview_urls: list[str]) -> str:
    parts = [header(post_at, "news")]
    if preview_urls:
        parts.append(" ".join(f'<img src="{u}" width="180">' for u in preview_urls) + "\n")
    parts += [
        "## 큰 제목\n(표지 두 줄 제목, 각 7자 안팎)", f"{post['headline1']}\n{post['headline2']}\n",
        "## 표지 한 줄\n" + post["subtitle"] + "\n",
    ]
    for i, s in enumerate(post["slides"][:3], start=1):
        parts.append(f"## 카드 {i}\n제목: {s['heading']}\n{s['body']}\n")
    parts += [
        "## 마무리 문구\n" + post["closing"] + "\n",
        "## 출처\n" + "\n".join(f"- {s['name']} | {s['url']}" for s in post["sources"]) + "\n",
        "## 인스타 본문\n" + caption + "\n",
    ]
    return "\n".join(parts)


def news_from_body(body: str) -> dict:
    """사용자가 고친 뉴스 초안을 카드 데이터로 되돌린다."""
    secs = sections(body)
    head = lines_of(secs.get("큰 제목", ""))
    slides = []
    for i in (1, 2, 3):
        raw = [l for l in secs.get(f"카드 {i}", "").splitlines() if l.strip()]
        if not raw:
            continue
        heading = raw[0].split(":", 1)[1].strip() if raw[0].startswith("제목") and ":" in raw[0] else raw[0].strip()
        slides.append({"heading": heading, "body": " ".join(l.strip() for l in raw[1:])})
    sources = []
    for line in lines_of(secs.get("출처", "")):
        name, _, url = line.partition("|")
        sources.append({"name": name.strip(), "url": url.strip()})
    return {"headline1": head[0] if head else "", "headline2": head[1] if len(head) > 1 else "",
            "subtitle": " ".join(lines_of(secs.get("표지 한 줄", ""))), "slides": slides,
            "closing": " ".join(lines_of(secs.get("마무리 문구", ""))), "sources": sources,
            "caption": secs.get("인스타 본문", "").strip()}


def reel_from_body(body: str) -> dict:
    secs = sections(body)
    head = lines_of(secs.get("큰 제목", ""))
    return {"headline1": head[0] if head else "", "headline2": head[1] if len(head) > 1 else "",
            "subtitles": lines_of(secs.get("자막", "")), "caption": secs.get("인스타 본문", "").strip()}


ATTACH_RE = re.compile(r"https://(?:github\.com/user-attachments/(?:assets|files)/[\w\-./%]+|private-user-images\.githubusercontent\.com/[^\s)\"'>]+)")


def attachments(*texts: str) -> list[str]:
    """본문·댓글에 첨부된 사진·영상 주소 (봇이 올린 미리보기 주소는 제외)."""
    urls = []
    for t in texts:
        for u in ATTACH_RE.findall(t or ""):
            if u not in urls:
                urls.append(u)
    return urls
