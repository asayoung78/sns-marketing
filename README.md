# sns-marketing · 인스타그램 자동화

초등 교육·학급경영 카드뉴스를 AI(Claude)로 만들어 매일 저녁 인스타그램에 자동 게시하고, 댓글에 자동으로 답글을 다는 도구입니다.

- **설정 방법:** [docs/SETUP.md](docs/SETUP.md)
- **주제·말투·색상·답글 방식 변경:** [settings.toml](settings.toml)

## 구성
| 경로 | 역할 |
|---|---|
| `src/insta_auto/generate.py` | AI 원고 작성 + 카드뉴스 이미지 생성 |
| `src/insta_auto/publish.py` | 인스타그램 캐러셀 게시 |
| `src/insta_auto/reply.py` | 새 댓글 확인 + AI 답글 (draft/auto) |
| `src/insta_auto/refresh_token.py` | 인스타 토큰 60일 자동 연장 |
| `data/history.json` | 게시 기록 (주제 중복 방지) |
| `media/` | 생성된 카드 이미지 |

## 로컬 실행 (선택)
```bash
pip install -r requirements.txt   # 한글 글꼴: sudo apt install fonts-noto-cjk
export ANTHROPIC_API_KEY=... IG_ACCESS_TOKEN=...
PYTHONPATH=src python -m insta_auto.generate --topic "학부모 상담 준비"
```
