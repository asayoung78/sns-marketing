"""공공데이터 설정 점검: TourAPI 부산 코드·축제 조회, KOPIS 부산 공연 조회가 되는지 시험한다.

사용법: python -m insta_auto.check_tourapi
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_settings
from .sources import events


def check_kopis(today):
    print("\n③ 부산 공연 조회 시험 (KOPIS)")
    region = load_settings()["event"]["kopis_region"]
    try:
        found = events.kopis_list(today, 14, region)
        print(f"   조회 {len(found)}건 (오늘부터 14일 안에 공연하는 부산 공연)")
        for e in found[:10]:
            print(f"   - [{e['genre']}] {e['title']} ({e['start']} ~ {e['end']}) {e['venue']}")
        if found:
            ev = events.kopis_detail(found[0])
            print(f"   상세 시험: 관람료={ev['price'][:60]} / 시간={ev['time'][:60]}")
        else:
            print("   0건입니다. 인증키가 맞는지(앞뒤 공백 없이) 확인하세요.")
    except Exception as e:
        print(f"   조회 실패: {e}")


def main():
    region = load_settings()["event"]["tourapi_region"]
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    if not os.environ.get("TOURAPI_KEY", "").strip():
        print("TOURAPI_KEY 없음 → 축제 점검 건너뜀")
        return check_kopis(today)

    print("① 법정동 시도코드 목록 (ldongCode2)")
    try:
        rows = events._tour("ldongCode2", numOfRows=50, pageNo=1)
        for r in rows:
            print(f"   {r.get('code') or r.get('lDongRegnCd')} = {r.get('name') or r.get('lDongRegnNm')}")
        busan = [r for r in rows if "부산" in str(r.get("name") or r.get("lDongRegnNm"))]
        if busan:
            code = busan[0].get("code") or busan[0].get("lDongRegnCd")
            mark = "일치 ✅" if str(code) == str(region) else f"불일치 ❌ → settings.toml의 tourapi_region을 \"{code}\"로 바꾸세요"
            print(f"   → 부산 코드 {code} / 현재 설정 {region}: {mark}")
    except Exception as e:
        print(f"   조회 실패: {e}")

    print("\n② 부산 축제 조회 시험 (searchFestival2)")
    try:
        found = events.tour_list(today, 14, region)
        upcoming = [e for e in found if e["end"] and e["end"] >= today]
        print(f"   조회 {len(found)}건 / 진행 중·예정 {len(upcoming)}건")
        for e in upcoming[:10]:
            print(f"   - {e['title']} ({e['start']} ~ {e['end']}) {e['address']}")
        if not found:
            print("   0건입니다. 키 승인 여부(승인 후 1시간~1일 소요)와 지역코드를 확인하세요.")
    except Exception as e:
        print(f"   조회 실패: {e}")
    check_kopis(today)


if __name__ == "__main__":
    main()
