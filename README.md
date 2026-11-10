# sns-marketing · 부산온나우 인스타그램 자동화

부산의 공연·전시·축제와 부산 뉴스를 카드뉴스로 만들어 매일 저녁 인스타그램(부산온나우)에 자동 게시하고, 댓글에 자동으로 답글을 다는 도구입니다.

- 공연: KOPIS 오픈API / 축제·행사: 한국관광공사 TourAPI / 전시·뉴스: AI 웹 조사(공식 출처 확인)

- **설정 방법:** [docs/SETUP.md](docs/SETUP.md)
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
