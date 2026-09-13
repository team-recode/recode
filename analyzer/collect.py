"""PHASE 2 — GitHub 저장소를 repos/ 아래로 clone하고 메타데이터를 추출한다.

사용법:
    py -m analyzer.collect https://github.com/psf/requests
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPOS_DIR = Path(__file__).resolve().parent.parent / "repos"

# clone이 이 시간을 넘으면 중단한다. 대형 저장소로 세션이 묶이는 것을 막는다.
CLONE_TIMEOUT_SEC = 300

# https://github.com/owner/repo, 끝의 .git 과 슬래시는 허용한다.
GITHUB_URL_RE = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


class CollectError(Exception):
    """수집 실패. 메시지를 사용자에게 그대로 보여준다."""


def parse_repo_url(url: str) -> tuple[str, str]:
    """GitHub URL에서 (owner, repo)를 뽑는다."""
    match = GITHUB_URL_RE.match(url.strip())
    if not match:
        raise CollectError(
            f"GitHub 저장소 URL이 아닙니다: {url}\n"
            "형식: https://github.com/owner/repo"
        )
    return match.group(1), match.group(2)


def _git(args: list[str], cwd: Path | None = None, timeout: int = 30) -> str:
    """git 명령을 실행하고 stdout을 돌려준다. 실패하면 stderr를 담아 올린다."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise CollectError("git 명령을 찾을 수 없습니다. git 설치와 PATH를 확인하세요.")
    except subprocess.TimeoutExpired:
        raise CollectError(f"git {args[0]} 명령이 {timeout}초를 넘겨 중단했습니다.")

    if result.returncode != 0:
        raise CollectError(
            f"git {args[0]} 실패 (exit {result.returncode})\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def clone(url: str, owner: str, repo: str) -> Path:
    """repos/{owner}__{repo} 로 clone한다. 이미 있으면 그대로 쓴다."""
    clone_path = REPOS_DIR / f"{owner}__{repo}"

    if (clone_path / ".git").is_dir():
        return clone_path

    if clone_path.exists():
        raise CollectError(
            f"{clone_path} 가 이미 있지만 git 저장소가 아닙니다. 삭제 후 다시 실행하세요."
        )

    REPOS_DIR.mkdir(exist_ok=True)
    # commit_count 와 이후 PHASE 4(High-Churn)가 전체 이력을 필요로 하므로 얕은 clone을 쓰지 않는다.
    _git(["clone", url, str(clone_path)], timeout=CLONE_TIMEOUT_SEC)
    return clone_path


def collect(url: str) -> dict:
    """저장소를 확보하고 분석에 필요한 메타데이터를 돌려준다."""
    owner, repo = parse_repo_url(url)
    clone_path = clone(url, owner, repo)

    return {
        "owner": owner,
        "repo": repo,
        "clone_path": clone_path.relative_to(REPOS_DIR.parent).as_posix(),
        "default_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=clone_path),
        "commit_count": int(_git(["rev-list", "--count", "HEAD"], cwd=clone_path)),
        "head_sha": _git(["rev-parse", "HEAD"], cwd=clone_path),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("사용법: py -m analyzer.collect https://github.com/owner/repo", file=sys.stderr)
        return 2

    try:
        print(json.dumps(collect(sys.argv[1]), indent=2, ensure_ascii=False))
    except CollectError as exc:
        print(f"수집 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
