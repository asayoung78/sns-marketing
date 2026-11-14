# sns-marketing · 부산온나우 인스타그램 자동화

부산 공연·축제·전시는 **릴스**(이틀에 1번), 부산 뉴스는 **카드뉴스**(월·수·금)로 초안을 만들고, 사용자가 다듬어 **승인한 것만** 인스타그램(부산온나우)에 게시하는 반자동 도구입니다. 알림은 텔레그램으로 옵니다.

- 공연: KOPIS 오픈API / 축제·행사: 한국관광공사 TourAPI / 전시·뉴스: AI 웹 조사(공식 출처 확인)

- **매일 쓰는 법:** [docs/운영가이드.md](docs/운영가이드.md)
- **처음 설정:** [docs/SETUP.md](docs/SETUP.md)
- **요일별 종류·말투·색상·답글 방식 변경:** [settings.toml](settings.toml)
- **행사 직접 추가:** [data/manual_events.csv](data/manual_events.csv)

## 구성
| 경로 | 역할 |
|---|---|
| `src/insta_auto/generate.py` | 요일별 종류 선택 → 원고 작성 → 카드뉴스 이미지 생성 |
| `src/insta_auto/sources/events.py` | KOPIS·TourAPI·직접 입력 행사 수집 |
| `src/insta_auto/publish.py` | 인스타그램 캐러셀 게시 |
| `src/insta_auto/reply.py` | 새 댓글 확인 + AI 답글 (draft/auto) |
| `src/insta_auto/refresh_token.py` | 인스타 토큰 60일 자동 연장 |
| `data/history.json` | 게시 기록 (주제 중복 방지) |
| `media/` | 생성된 카드 이미지 |

## 로컬 실행 (선택)
```bash
pip install -r requirements.txt   # 한글 글꼴: sudo apt install fonts-noto-cjk
export ANTHROPIC_API_KEY=... KOPIS_API_KEY=... TOURAPI_KEY=...
PYTHONPATH=src python -m insta_auto.generate --kind event
```
