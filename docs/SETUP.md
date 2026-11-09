# 인스타그램 자동화 설정 안내서

> 처음 한 번만 설정하면 됩니다. 소요 시간은 약 30~40분입니다.
> Meta 개발자 화면의 메뉴 이름은 자주 바뀌므로, 아래와 조금 다르면 비슷한 이름의 메뉴를 찾아 주세요.

## 0. 전체 구조

| 기능 | 실행 시각 | 담당 파일 |
|---|---|---|
| 카드뉴스 생성 + 게시 | 매일 19:20 (한국 시간) | `.github/workflows/post.yml` |
| 댓글 자동 답글 | 07~23시, 매시 7분 | `.github/workflows/reply.yml` |
| 토큰 자동 연장 | 매월 1일·15일 | `.github/workflows/refresh-token.yml` |
| 주제·말투·색상·답글 방식 | (설정) | `settings.toml` |

---

## 1. GitHub 저장소를 공개(Public)로 전환

Instagram은 이미지를 **공개 주소(URL)** 로만 받습니다. 기본 설정(`hosting.method = "github"`)은 이 저장소에 올린 이미지 주소를 사용하므로 저장소가 공개되어 있어야 합니다.

- 경로: 저장소 → **Settings** → 맨 아래 **Danger Zone** → **Change visibility** → Public
- 비밀 정보(API 키, 토큰)는 코드가 아니라 Secrets에 저장하므로 공개해도 노출되지 않습니다.
- 비공개로 두고 싶다면 → [부록 A. Cloudinary 사용](#부록-a-저장소를-비공개로-두고-싶을-때-cloudinary)

## 2. Meta 개발자 앱 만들기 → Instagram 토큰 발급

1. https://developers.facebook.com 접속 → 페이스북 계정으로 로그인 → **내 앱** → **앱 만들기**
2. 사용 사례에서 **Instagram에서 메시지 및 콘텐츠 관리**(Instagram API) 선택 → 앱 이름 입력 후 생성
3. 왼쪽 메뉴 **Instagram** → **API 설정(Instagram 로그인 방식)** 으로 이동
4. **계정 추가** → 자동화할 인스타그램 계정으로 로그인 → 권한 허용
   - 필요한 권한: `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`
5. 계정 옆 **토큰 생성** 클릭 → 표시된 **액세스 토큰**을 복사해 둡니다 (유효기간 60일, 이후 자동 연장)

> 본인 계정만 쓰는 경우 **앱 검수(App Review)는 필요 없습니다.** 앱이 '개발 모드'여도 앱 관리자 본인 계정에는 동작합니다.

## 3. Anthropic(Claude) API 키 발급

1. https://console.anthropic.com 가입 → **Billing**에서 크레딧 충전 (최소 금액으로 시작)
2. **API Keys** → **Create Key** → 키 복사

## 4. GitHub Personal Access Token 발급 (토큰 자동 연장용)

1. GitHub 오른쪽 위 프로필 → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
2. Repository access: **Only select repositories** → `sns-marketing` 선택
3. Permissions → Repository permissions → **Secrets: Read and write**
4. 만료일은 최대(1년)로 설정 → 생성된 토큰 복사

## 5. GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | 3단계에서 복사한 Claude API 키 |
| `IG_ACCESS_TOKEN` | 2단계에서 복사한 인스타그램 토큰 |
| `GH_PAT` | 4단계에서 복사한 GitHub 토큰 |

## 6. 설정 파일 수정

`settings.toml`을 열어(GitHub 웹에서 연필 아이콘) 다음을 바꿉니다.

- `handle` → 실제 인스타그램 아이디 (예: `@happy_teacher`)
- `topic_pool` → 다루고 싶은 주제 추가·삭제
- `[design]` 색상 → 원하는 색상 코드로 변경 (선택)

## 7. 첫 테스트 (게시하지 않고 미리보기)

1. 저장소 → **Actions** → **인스타 게시물 자동 업로드** → **Run workflow**
2. `미리보기만` 체크 ✅ 상태로 실행
3. 완료 후 실행 화면 아래 **Artifacts → preview** 내려받기 → 카드 이미지와 `post.json`(본문) 확인
4. 마음에 들면 같은 화면에서 `미리보기만` 체크 해제 후 실행 → 실제 게시

## 8. 댓글 답글 운영 순서 (권장)

| 기간 | 설정 | 확인 방법 |
|---|---|---|
| 처음 2~3주 | `settings.toml` → `[reply] mode = "draft"` | Actions → **댓글 자동 답글** → 실행 기록의 **Summary** 표에서 초안 확인 |
| 이후 | `mode = "auto"` 로 변경 | 같은 Summary 표에서 등록 내역 확인 |

- 민감 키워드(`manual_keywords`)가 들어간 댓글이나 AI가 '사람 확인 필요'로 판단한 댓글은 자동 답글 없이 **직접 확인** 으로 표시됩니다.
- 이미 내가 답글을 단 댓글은 건너뛰므로 중복 답글은 생기지 않습니다.

## 9. 예상 비용 (추정치)

| 항목 | 비용 |
|---|---|
| GitHub Actions | 공개 저장소는 무료 |
| Claude API – 게시물 1건 | 약 100~200원 수준 (추정) |
| Claude API – 답글 1건 | 약 10원 내외 (추정) |
| Instagram API | 무료 |

> 실제 비용은 console.anthropic.com → **Usage** 에서 확인하세요. 비용을 줄이려면 `settings.toml`의 `model`을 `claude-sonnet-5-5`로 바꾸면 됩니다.

## 10. 문제 해결

| 증상 | 원인·조치 |
|---|---|
| `Instagram API 오류 400 ... image_url` | 저장소가 비공개입니다 → 1단계 확인 |
| `Instagram API 오류 190` | 토큰 만료 → 2단계에서 토큰 재발급 후 `IG_ACCESS_TOKEN` 교체 |
| `Instagram API 오류 ... version` | `settings.toml`의 `api_version`을 Meta 최신 버전으로 변경 |
| 게시 시각이 늦어짐 | GitHub 예약 실행은 수십 분 늦어질 수 있습니다. 시각은 `post.yml`의 `cron`에서 변경 (한국 시간 − 9시간) |
| 하루 쉬고 싶을 때 | Actions → 해당 워크플로 → 오른쪽 위 `⋯` → **Disable workflow** |

---

## 부록 A. 저장소를 비공개로 두고 싶을 때 (Cloudinary)

1. https://cloudinary.com 무료 가입 → Dashboard에서 **Cloud name, API Key, API Secret** 확인
2. GitHub Secrets에 `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` 등록
3. `settings.toml` → `[hosting] method = "cloudinary"`
4. 비공개 저장소의 GitHub Actions는 월 2,000분까지 무료입니다. 댓글 확인 주기(`reply.yml`)를 2시간 간격으로 늘리는 것을 권장합니다.
