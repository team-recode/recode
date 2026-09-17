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
from judge import languages

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
    """분석 대상 .py 파일을 저장소 루트 기준 상대 경로로 돌려준다.

    이름 그대로 Python 전용이다. vulture 가 Python 만 읽기 때문에 dead-code 는
    다른 언어로 넓히지 못했다. high_churn 은 언어를 가리지 않는다.
    """
    for path in clone_path.rglob("*.py"):
        if not languages.is_excluded(path.relative_to(clone_path).as_posix()):
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
        elif line and commit_date and languages.detect(line) is not None:
            # 언어를 가리지 않는다. git 이력은 파서가 필요 없으므로 지원 언어 전부를 센다.
            # HTML 처럼 함수 비교를 못 하는 언어도 "자주 바뀐 파일" 로는 알려줄 수 있다.
            if not languages.is_excluded(line):
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


# 파일 밖에서 못 부르는 함수가 자기 파일 안에서도 한 번(정의 자리)밖에 안 나오면
# 호출되는 자리가 없다는 뜻이다. 추측이 아니라 그 파일만 보면 확정된다.
# vulture 가 Python 전용이라 다른 언어는 이 방식으로 본다.
FILE_LOCAL_CONFIDENCE = 90

# 코드가 직접 부르지 않고 런타임·프레임워크가 부르는 이름들. 호출 자리가 없는 게 정상이다.
# Java 직렬화 훅(writeReplace 등)은 JVM 이 리플렉션으로 부른다. 빼지 않으면
# gson 의 LazilyParsedNumber 가 "안 쓰는 코드" 로 잡힌다(실측).
ENTRY_POINT_NAMES = {
    "main", "Main", "run", "Run",
    "setUp", "tearDown", "SetUp", "TearDown",
    "Dispose", "ToString", "Equals", "GetHashCode", "toString", "hashCode", "equals",
    "writeReplace", "readResolve", "writeObject", "readObject", "finalize",
}


def dead_code_by_scope(clone_path: Path) -> list[dict]:
    """Python 외 언어의 사용 근거 확인(16.2).

    `private` 메서드 · `static` 함수 · export 하지 않은 함수는 그 파일 밖에서 부를 수 없다.
    그러므로 자기 파일 안에서 이름이 정의 자리 한 번만 나오면 호출되는 자리가 없다.
    저장소 전체를 훑어 "아마 안 쓰일 것" 이라고 추측하는 방식보다 오탐이 적다.
    공개 API 는 저장소 밖에서 불릴 수 있으므로 처음부터 대상에 넣지 않는다.
    """
    candidates = []
    for path, rel, lang in languages.iter_source_files(clone_path):
        if lang.grammar is None or not lang.analyzable:
            continue          # Python 은 vulture 가 본다
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            functions = languages.extract_functions(text, rel, lang, 0)
        except Exception:                             # noqa: BLE001
            continue          # 못 읽은 파일은 근거가 되지 못한다. 추측하지 않는다
        if not functions:
            continue

        # 파싱이 깨진 파일로는 "안 쓰인다" 고 단정하지 않는다. 근거가 틀린 자리에서 나온다.
        # 실제로 spdlog 의 `class SPDLOG_API mdc {` 는 매크로 때문에 클래스로 안 읽혀
        # 공개 static 멤버가 파일 한정으로 잡혔고, serilog 의 `#if` 전처리기 블록은
        # `new SafeAggregateEnricher(...)` 를 메서드 선언으로 읽었다.
        if languages.has_parse_error(text, lang):
            continue

        # 이름이 식별자로 몇 번 나오는지 센다. 주석·문자열은 식별자가 아니라 안 잡힌다.
        counts = languages.identifier_counts(text, lang)
        for func in functions:
            if not func.get("file_local") or func["name"] in ENTRY_POINT_NAMES:
                continue
            if counts.get(func["name"], 0) > 1:
                continue      # 정의 말고 다른 자리에서도 나온다. 쓰이고 있다
            candidates.append({
                "file": rel,
                "name": func["name"],
                "kind": "function",
                "line": func["start_line"],
                "confidence": FILE_LOCAL_CONFIDENCE,
                "message": DEAD_CODE_MESSAGE,
            })
    return candidates


def dead_code(clone_path: Path,
              min_confidence: int = VULTURE_MIN_CONFIDENCE) -> list[dict]:
    """사용 근거를 찾지 못한 함수/변수 후보를 돌려준다(16.2).

    Python 은 vulture, 나머지 언어는 스코프 기반(`dead_code_by_scope`)으로 본다.
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

    # Python 외 언어는 스코프 기반으로 본다. 두 결과를 합쳐 하나의 목록으로 돌려준다.
    candidates += dead_code_by_scope(clone_path)

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
