"""장기 토큰(60일)을 연장하고 새 토큰을 stdout이 아닌 파일로 넘긴다.

사용법: python -m insta_auto.refresh_token <출력 파일>
워크플로가 이 파일을 읽어 GitHub Secret(IG_ACCESS_TOKEN)을 갱신한다.
"""

import sys

from .config import require_env
from .instagram import refresh_long_lived_token


def main():
    result = refresh_long_lived_token(require_env("IG_ACCESS_TOKEN"))
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write(result["access_token"])
    days = int(result.get("expires_in", 0)) // 86400
    print(f"토큰 갱신 완료: 약 {days}일 후 만료")


if __name__ == "__main__":
    main()
