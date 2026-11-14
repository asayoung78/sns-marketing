"""공공데이터 설정 점검: TourAPI 부산 코드·축제 조회, KOPIS 부산 공연 조회가 되는지 시험한다.

사용법: python -m insta_auto.check_tourapi
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .config import load_settings
from .drive import folder_id
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


def check_drive():
    print("\n④ 구글 드라이브 영상 폴더 확인")
    key, raw = os.environ.get("GDRIVE_API_KEY", "").strip(), os.environ.get("GDRIVE_FOLDER_ID", "")
    folder = folder_id(raw)
    shape = "주소 전체" if "drive.google.com" in raw else ("따옴표·공백 포함" if raw.strip(" '\"\n") != raw else "ID만")
    print(f"   폴더 ID 입력 형태: {shape} / 추출한 ID: {folder[:4]}…{folder[-3:]} ({len(folder)}자)" if folder else "   폴더 ID를 찾지 못함")
    if not key or not folder:
        print("   GDRIVE_API_KEY 또는 GDRIVE_FOLDER_ID 없음 → 건너뜀")
        return
    try:
        resp = requests.get("https://www.googleapis.com/drive/v3/files", timeout=30, params={
            "q": f"'{folder}' in parents and trashed = false", "key": key,
            "fields": "files(name,mimeType,size)", "pageSize": 50})
        if not resp.ok:
            print(f"   조회 실패 {resp.status_code}: {resp.text[:300]}")
            print("   → 폴더가 '링크가 있는 모든 사용자 보기'로 공유됐는지, 폴더 ID가 맞는지 확인하세요.")
            return
        files = resp.json().get("files", [])
        print(f"   연결 성공 ✅ 파일 {len(files)}개")
        for f in files[:10]:
            mb = int(f.get("size", 0)) / 1_000_000
            print(f"   - {f['name']} ({f['mimeType']}, {mb:.1f}MB)")
    except Exception as e:
        print(f"   조회 실패: {e}")


def check_telegram():
    print("\n⑤ 텔레그램 알림 확인")
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        print("   TELEGRAM_BOT_TOKEN 없음 → 건너뜀")
        return
    base = f"https://api.telegram.org/bot{token}"
    try:
        if not chat:
            # 봇에게 먼저 아무 메시지나 보낸 뒤 실행하면 대화방 번호(chat id)를 알려 준다
            updates = requests.get(f"{base}/getUpdates", timeout=30).json().get("result", [])
            chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "") for u in updates if "message" in u}
            if chats:
                for cid, name in chats.items():
                    print(f"   대화방 번호(TELEGRAM_CHAT_ID): {cid}")
            else:
                print("   대화 기록 없음 → 텔레그램에서 봇에게 /start 를 보낸 뒤 다시 실행하세요.")
            return
        resp = requests.post(f"{base}/sendMessage", timeout=30,
                             json={"chat_id": chat, "text": "✅ 부산온나우 알림 연결 테스트 성공! 앞으로 릴스 기획표와 초안 알림을 여기로 보낼게요."})
        print("   테스트 메시지 전송 성공 ✅" if resp.ok else f"   전송 실패 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"   확인 실패: {type(e).__name__}")  # 토큰이 오류 메시지에 섞여 나오지 않게 종류만 표시


def main():
    region = load_settings()["event"]["tourapi_region"]
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    if not os.environ.get("TOURAPI_KEY", "").strip():
        print("TOURAPI_KEY 없음 → 축제 점검 건너뜀")
        check_kopis(today)
        check_drive()
        return check_telegram()

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
    check_drive()
    check_telegram()


if __name__ == "__main__":
    main()
