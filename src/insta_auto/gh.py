"""GitHub 이슈(초안) 읽기·쓰기. 워크플로의 GITHUB_TOKEN, GITHUB_REPOSITORY를 사용한다."""

import os

import requests

API = "https://api.github.com"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}  # 공개 저장소라 이 사람들의 댓글만 명령으로 인정


def _repo() -> str:
    return os.environ["GITHUB_REPOSITORY"]


def _call(method: str, path: str, **kw):
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    resp = requests.request(method, f"{API}/repos/{_repo()}/{path}", headers=headers, timeout=30, **kw)
    if not resp.ok:
        raise RuntimeError(f"GitHub API 오류 {resp.status_code} ({method} {path}): {resp.text[:300]}")
    return resp.json() if resp.content else {}


def issue_url(number: int) -> str:
    return f"https://github.com/{_repo()}/issues/{number}"


def create_issue(title: str, body: str, labels: list[str]) -> dict:
    return _call("POST", "issues", json={"title": title, "body": body, "labels": labels})


def update_issue(number: int, **fields) -> dict:
    return _call("PATCH", f"issues/{number}", json=fields)


def get_issue(number: int) -> dict:
    return _call("GET", f"issues/{number}")


def list_issues(label: str, state: str = "open") -> list[dict]:
    items, page = [], 1
    while True:
        batch = _call("GET", "issues", params={"labels": label, "state": state, "per_page": 100, "page": page})
        items += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            return items
        page += 1


def comments(number: int) -> list[dict]:
    return _call("GET", f"issues/{number}/comments", params={"per_page": 100})


def comment(number: int, body: str) -> dict:
    return _call("POST", f"issues/{number}/comments", json={"body": body})


def add_labels(number: int, labels: list[str]):
    _call("POST", f"issues/{number}/labels", json={"labels": labels})


def remove_label(number: int, label: str):
    try:
        _call("DELETE", f"issues/{number}/labels/{requests.utils.quote(label)}")
    except RuntimeError:
        pass


def ensure_labels(specs: dict[str, str]):
    """처음 실행할 때 필요한 라벨(이름: 색)을 만든다."""
    have = {l["name"] for l in _call("GET", "labels", params={"per_page": 100})}
    for name, color in specs.items():
        if name not in have:
            _call("POST", "labels", json={"name": name, "color": color})


def trusted_comments(number: int) -> list[dict]:
    return [c for c in comments(number) if c.get("author_association") in TRUSTED]
