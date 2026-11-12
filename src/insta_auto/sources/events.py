"""부산 공연·축제 정보를 공공데이터에서 모은다.

- 공연: KOPIS(공연예술통합전산망) 오픈API  → 환경 변수 KOPIS_API_KEY
- 축제·행사: 한국관광공사 TourAPI(KorService2) → 환경 변수 TOURAPI_KEY (공공데이터포털 '일반 인증키(Decoding)')
- 직접 추가: data/manual_events.csv (공공데이터에 없는 전시·행사)

모든 출처의 행사를 같은 모양(dict)으로 맞춘다. 카드의 날짜·장소·가격은 이 값을 그대로 쓴다(AI가 바꾸지 않음).
"""

import csv
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

from ..config import ROOT

KOPIS_BASE = "http://www.kopis.or.kr/openApi/restful"
TOUR_BASE = "https://apis.data.go.kr/B551011/KorService2"


def _d(text: str) -> date | None:
    text = (text or "").strip().replace(".", "").replace("-", "")
    try:
        return datetime.strptime(text[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _clean_title(text: str) -> str:
    """KOPIS 제목·공연장 끝의 지역 표시 ' [부산]'을 뗀다."""
    return re.sub(r"\s*\[부산\]", "", text or "").strip()


def _event(**kw) -> dict:
    base = dict(id="", source="", category="", title="", start=None, end=None, venue="", address="",
                time="", price="", age="", contact="", url="", description="", genre="")
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


# ---------------- KOPIS (공연) ----------------
def kopis_list(today: date, days: int, region: str) -> list[dict]:
    key = os.environ.get("KOPIS_API_KEY", "").strip()
    if not key:
        print("KOPIS_API_KEY 없음 → 공연 정보 건너뜀")
        return []
    events = []
    # 한 번 조회에 최대 100건까지만 주므로 '공연중(02)'과 '공연예정(01)'을 나눠 조회한다
    for state in ("02", "01"):
        params = {"service": key, "stdate": today.strftime("%Y%m%d"),
                  "eddate": (today + timedelta(days=min(days, 31))).strftime("%Y%m%d"),
                  "cpage": 1, "rows": 100, "signgucode": region, "prfstate": state}
        root = ET.fromstring(requests.get(f"{KOPIS_BASE}/pblprfr", params=params, timeout=30).content)
        for db in root.findall("db"):
            g = lambda tag: (db.findtext(tag) or "").strip()
            events.append(_event(id=f"kopis:{g('mt20id')}", source="KOPIS", category="공연", title=_clean_title(g("prfnm")),
                                 start=_d(g("prfpdfrom")), end=_d(g("prfpdto")), venue=_clean_title(g("fcltynm")),
                                 genre=g("genrenm")))
    return events


def kopis_detail(ev: dict) -> dict:
    key = os.environ["KOPIS_API_KEY"].strip()
    mt20id = ev["id"].split(":", 1)[1]
    root = ET.fromstring(requests.get(f"{KOPIS_BASE}/pblprfr/{mt20id}", params={"service": key}, timeout=30).content)
    db = root.find("db")
    if db is None:
        return ev
    g = lambda tag: (db.findtext(tag) or "").strip()
    links = [(r.findtext("relatenm") or "").strip() for r in db.findall("relates/relate")]
    ev.update(time=g("dtguidance"), price=g("pcseguidance"), age=g("prfage"),
              contact=", ".join(l for l in links if l),
              description=" ".join(x for x in [g("prfcast") and f"출연: {g('prfcast')}", g("prfruntime") and f"공연시간: {g('prfruntime')}", g("sty")] if x),
              url=f"https://www.kopis.or.kr/por/db/pblprfr/pblprfrView.do?mt20Id={mt20id}")
    return ev


# ---------------- TourAPI (축제·행사) ----------------
def _tour(op: str, **params) -> list[dict]:
    params.update(serviceKey=os.environ["TOURAPI_KEY"].strip(), MobileOS="ETC", MobileApp="BusanOnNow", _type="json")
    resp = requests.get(f"{TOUR_BASE}/{op}", params=params, timeout=30)
    resp.raise_for_status()
    body = resp.json().get("response", {}).get("body", {})
    items = body.get("items") or {}
    item = items.get("item", []) if isinstance(items, dict) else []
    return item if isinstance(item, list) else [item]


def tour_list(today: date, days: int, region: str) -> list[dict]:
    if not os.environ.get("TOURAPI_KEY", "").strip():
        print("TOURAPI_KEY 없음 → 축제 정보 건너뜀")
        return []
    # 이미 시작한 축제도 잡기 위해 60일 전부터 조회한 뒤 기간으로 거른다
    items = _tour("searchFestival2", eventStartDate=(today - timedelta(days=60)).strftime("%Y%m%d"),
                  lDongRegnCd=region, numOfRows=200, pageNo=1, arrange="C")
    events = []
    for it in items:
        events.append(_event(id=f"tour:{it.get('contentid')}", source="한국관광공사", category="축제·행사",
                             title=it.get("title", ""), start=_d(it.get("eventstartdate")), end=_d(it.get("eventenddate")),
                             address=it.get("addr1", ""), contact=it.get("tel", "")))
    return events


def tour_detail(ev: dict) -> dict:
    cid = ev["id"].split(":", 1)[1]
    intro = (_tour("detailIntro2", contentId=cid, contentTypeId=15) or [{}])[0]
    common = (_tour("detailCommon2", contentId=cid) or [{}])[0]
    clean = lambda s: (s or "").replace("<br>", " ").replace("<br />", " ").strip()
    ev.update(venue=clean(intro.get("eventplace")) or ev["address"], time=clean(intro.get("playtime")),
              price=clean(intro.get("usetimefestival")), age=clean(intro.get("agelimit")),
              contact=clean(intro.get("sponsor1tel")) or ev["contact"],
              description=clean(common.get("overview"))[:1500],
              url=f"https://korean.visitkorea.or.kr/detail/fes_detail.do?cotid={cid}")
    return ev


# ---------------- 직접 입력 ----------------
def manual_list() -> list[dict]:
    path = ROOT / "data" / "manual_events.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [_event(**{**row, "id": f"manual:{row['id']}", "source": "직접 입력",
                          "start": _d(row.get("start")), "end": _d(row.get("end"))})
                for row in csv.DictReader(f) if row.get("id") and row.get("title")]


DETAIL = {"KOPIS": kopis_detail, "한국관광공사": tour_detail}


def candidates(settings: dict, today: date, posted_ids: set[str]) -> list[dict]:
    cfg = settings["event"]
    days = cfg["lookahead_days"]
    pool = []
    for fetch in (lambda: kopis_list(today, days, cfg["kopis_region"]),
                  lambda: tour_list(today, days, cfg["tourapi_region"]),
                  manual_list):
        try:
            pool += fetch()
        except Exception as e:  # 한 출처가 실패해도 나머지로 진행
            print(f"행사 수집 실패: {e}")
    horizon = today + timedelta(days=days)
    out, seen = [], set()
    for ev in pool:
        if ev["id"] in posted_ids or ev["title"] in seen or not ev["start"] or not ev["end"]:
            continue
        if ev["end"] < today or ev["start"] > horizon:
            continue
        seen.add(ev["title"])
        out.append(ev)
    # 직접 입력 우선, 그다음 곧 시작하거나 진행 중인 순
    out.sort(key=lambda e: (e["source"] != "직접 입력", max(e["start"], today)))
    return out


def with_detail(ev: dict) -> dict:
    fn = DETAIL.get(ev["source"])
    if fn:
        try:
            return fn(ev)
        except Exception as e:
            print(f"상세 정보 조회 실패({ev['id']}): {e}")
    return ev


def period_text(ev: dict) -> str:
    s, e = ev["start"], ev["end"]
    fmt = lambda d: f"{d.year}.{d.month:02d}.{d.day:02d}"
    return fmt(s) if s == e else f"{fmt(s)} ~ {fmt(e)}"
