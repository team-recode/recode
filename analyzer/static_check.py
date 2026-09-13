"""PHASE 4 — 정적 Evidence 생성 (16.1 High-Churn Hotspot, 16.2 Dead-Code Candidate).

사용법:
    py -m analyzer.static_check repos/psf__requests
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from analyzer.collect import CollectError, _git

# 분석 대상에서 제외하는 디렉터리. 생성 코드와 vendor 코드는 원저자의 손이 닿지 않는다.
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "build", "dist", "vendor", "third_party", ".tox", ".mypy_cache",
}

CHURN_WINDOW_DAYS = 60
CHURN_TOP_N = 20
VULTURE_MIN_CONFIDENCE = 60
VULTURE_EXIT_INVALID_ARGS = 2

# 근거의 한계를 그대로 드러내는 문구. 단정하지 않는다(16.2 / 10.2 ③).
DEAD_CODE_MESSAGE = "정적 호출 경로에서 사용 근거를 찾지 못했습니다."

# vulture 출력: path:line: unused function 'name' (60% confidence)
VULTURE_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+): unused (?P<kind>[\w ]+) '(?P<name>[^']+)' "
    r"\((?P<confidence>\d+)% confidence\)$"
)


def iter_python_files(clone_path: Path):
    """분석 대상 .py 파일을 저장소 루트 기준 상대 경로로 돌려준다."""
    for path in clone_path.rglob("*.py"):
        if EXCLUDE_DIRS.isdisjoint(path.relative_to(clone_path).parts):
            yield path


def high_churn(clone_path: Path, days: int = CHURN_WINDOW_DAYS,
               top_n: int = CHURN_TOP_N) -> list[dict]:
    """최근 N일간 변경 횟수가 많은 파일을 돌려준다(16.1).

    변경 횟수는 git 이력에서 센 객관적 수치일 뿐, 원저자가 헤맨 흔적이 아니다.
    출력 키는 16.1이 정한 `commits_60d` 고정이므로 days를 바꿔 부르면 키 이름과 창이 어긋난다.
    """
    # %x00 을 커밋 구분자로 써서 커밋 헤더와 파일 목록을 구분한다.
    log = _git(
        ["log", f"--since={days} days ago", "--pretty=format:%x00%aI", "--name-only"],
        cwd=clone_path,
        timeout=120,
    )

    commits = defaultdict(int)
    last_changed = {}
    commit_date = None

    for line in log.splitlines():
        if line.startswith("\x00"):
            commit_date = line[1:11]  # ISO 8601 앞 10자 = YYYY-MM-DD
        elif line and commit_date and line.endswith(".py"):
            if EXCLUDE_DIRS.isdisjoint(Path(line).parts):
                commits[line] += 1
                # git log는 최신순이므로 첫 등장이 가장 최근 변경이다.
                last_changed.setdefault(line, commit_date)

    results = [
        {"file": file, "commits_60d": count, "last_changed": last_changed[file]}
        for file, count in commits.items()
        # 삭제된 파일은 이후 단계가 열 수 없으므로 제외한다.
        if (clone_path / file).is_file()
    ]
    results.sort(key=lambda row: (-row["commits_60d"], row["file"]))
    return results[:top_n]


def dead_code(clone_path: Path,
              min_confidence: int = VULTURE_MIN_CONFIDENCE) -> list[dict]:
    """vulture가 사용 근거를 찾지 못한 함수/변수 후보를 돌려준다(16.2).

    삭제 권고가 아니라 확인이 필요한 후보다.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "vulture", str(clone_path),
             "--min-confidence", str(min_confidence),
             "--exclude", ",".join(f"*/{d}/*" for d in sorted(EXCLUDE_DIRS))],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise CollectError("vulture 실행이 300초를 넘겨 중단했습니다.")

    # vulture 종료 코드: 0 NoDeadCode / 1 InvalidInput / 2 InvalidCmdlineArguments / 3 DeadCode.
    # 3은 후보를 찾았다는 뜻이라 실패가 아니다. 1은 문법 오류 파일만 건너뛰고 나머지 스캔은 계속된다.
    if result.returncode == VULTURE_EXIT_INVALID_ARGS:
        raise CollectError(
            f"vulture 실행 인자 오류 (exit {result.returncode})\n{result.stderr.strip()}"
        )

    candidates = []
    for line in result.stdout.splitlines():
        match = VULTURE_LINE_RE.match(line.strip())
        if not match:
            continue
        candidates.append({
            "file": Path(match.group("file")).relative_to(clone_path).as_posix(),
            "name": match.group("name"),
            "kind": match.group("kind"),
            "line": int(match.group("line")),
            "confidence": int(match.group("confidence")),
            "message": DEAD_CODE_MESSAGE,
        })

    candidates.sort(key=lambda row: (-row["confidence"], row["file"], row["line"]))
    return candidates


def run(clone_path: Path) -> dict:
    """PHASE 4의 정적 Evidence 두 종류를 한 번에 생성한다."""
    if not (clone_path / ".git").is_dir():
        raise CollectError(f"git 저장소가 아닙니다: {clone_path}")

    return {
        "clone_path": clone_path.as_posix(),
        "high_churn": high_churn(clone_path),
        "dead_code": dead_code(clone_path),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("사용법: py -m analyzer.static_check repos/owner__repo", file=sys.stderr)
        return 2

    try:
        print(json.dumps(run(Path(sys.argv[1])), indent=2, ensure_ascii=False))
    except CollectError as exc:
        print(f"정적 분석 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
