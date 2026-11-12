"""TourAPI 설정값 점검: 부산 법정동 시도코드를 공식 API로 확인하고 축제 조회가 되는지 시험한다.

사용법: python -m insta_auto.check_tourapi
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import load_settings, require_env
from .sources import events


def main():
    require_env("TOURAPI_KEY")
    region = load_settings()["event"]["tourapi_region"]

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
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
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


if __name__ == "__main__":
    main()
