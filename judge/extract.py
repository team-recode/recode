"""PHASE 3 — 소스 파일에서 분석 가능한 함수 단위를 추출한다(15절).

PHASE 5(임베딩 후보 축소)에 넘길 표준 포맷을 만든다.
커밋 빈도가 높은 파일부터 처리하므로, 상한에 걸려 잘리더라도
가장 최근까지 손이 닿은 코드가 남는다.

사용법:
    py -m judge.extract repos/psf__requests
    py -m judge.extract repos/psf__requests --no-tests --json=cache/functions.json
"""

import ast
import json
import sys
from pathlib import Path

from analyzer.collect import CollectError
from analyzer.test_map import commit_counts
from judge import languages

# 언어별 규칙은 judge/languages.py 한 곳에서 관리한다.
# 예전에는 파일마다 제각각 판단해서 같은 파일을 어떤 데서는 테스트로, 어떤 데서는
# 아니라고 봤다(PHASE 12 자기참조 분석에서 실제로 걸린 문제다).
EXCLUDE_DIRS = languages.EXCLUDE_DIRS

# 15절 상한. 초과하면 commit 빈도 높은 파일부터 남긴다.
MAX_FUNCTIONS = 2000


def is_test_file(rel_path: Path) -> bool:
    """테스트 파일 판별. 언어마다 규칙이 다르므로 languages 에 맡긴다."""
    return languages.is_test_file(rel_path)


def signature_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """`async def` 여부와 반환 타입까지 담은 시그니처 문자열."""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    sig = f"{prefix}{node.name}({ast.unparse(node.args)})"
    if node.returns is not None:
        sig += f" -> {ast.unparse(node.returns)}"
    return sig


def iter_python_files(clone_path: Path):
    """분석 대상 .py 파일을 돌려준다."""
    for path in clone_path.rglob("*.py"):
        if not languages.is_excluded(path.relative_to(clone_path).as_posix()):
            yield path


def body_statements(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """본문 문장 수. 독스트링은 빼고 중첩까지 센다.

    최상위만 세면 "for 루프 하나로 된 20줄 함수"가 "return self._x" 와 같은 1개로 잡혀
    실제 후보가 통째로 걸러진다. PHASE 5 에서 겪은 문제다.
    """
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)             and isinstance(body[0].value.value, str):
        body = body[1:]
    return sum(len([n for n in ast.walk(stmt) if isinstance(n, ast.stmt)]) for stmt in body)


def extract_file(path: Path, rel: str, commit_count: int) -> list[dict]:
    """파일 하나에서 함수를 모두 뽑는다. 파싱 실패 파일은 근거로 쓸 수 없으므로 건너뛴다."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []

    lines = text.splitlines()
    is_test = is_test_file(Path(rel))
    out = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        out.append({
            "file": rel,
            "name": node.name,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "source": "\n".join(lines[node.lineno - 1:node.end_lineno]),
            "signature": signature_of(node),
            "docstring": ast.get_docstring(node),
            "commit_count": commit_count,
            # 15절: 테스트 파일도 추출은 하되 임베딩 후보에서는 필요에 따라 제외한다.
            "is_test": is_test,
            "lang": "python",
            "body_statements": body_statements(node),
        })
    return out


def extract(clone_path: Path, max_functions: int = MAX_FUNCTIONS,
            include_tests: bool = True) -> list[dict]:
    """저장소에서 함수를 추출한다. 상한을 넘으면 커밋 빈도 낮은 파일부터 버린다."""
    if not (clone_path / ".git").is_dir():
        raise CollectError(f"git 저장소가 아닙니다: {clone_path}")

    counts = commit_counts(clone_path)
    files = [(p, rel, lang) for p, rel, lang in languages.iter_source_files(clone_path)
             if lang.analyzable]
    if not include_tests:
        files = [fr for fr in files if not is_test_file(Path(fr[1]))]

    # 커밋이 잦은 파일부터 처리한다. 상한에 걸려도 손이 자주 닿은 코드가 남는다.
    files.sort(key=lambda fr: (-counts.get(fr[1], 0), fr[1]))

    functions = []
    for path, rel, lang in files:
        # 파일 단위로 자른다. 한 파일의 함수가 반만 남는 상황을 만들지 않는다.
        if len(functions) >= max_functions:
            break
        text = path.read_text(encoding="utf-8", errors="replace")
        if lang.grammar is None:
            functions.extend(extract_file(path, rel, counts.get(rel, 0)))
        else:
            try:
                functions.extend(
                    languages.extract_functions(text, rel, lang, counts.get(rel, 0)))
            except Exception:                 # noqa: BLE001
                # 문법이 파일 하나를 못 읽어도 저장소 전체 분석을 멈추지 않는다.
                # 근거로 쓸 수 없는 파일이니 조용히 건너뛴다. Python 쪽 SyntaxError 처리와 같다.
                continue

    return functions[:max_functions]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print("사용법: py -m judge.extract repos/owner__repo [--no-tests] [--json=파일]",
              file=sys.stderr)
        return 2

    try:
        # 15절: 테스트 파일도 추출은 한다. 빼는 것은 부르는 쪽 선택이다.
        functions = extract(Path(args[0]), include_tests="--no-tests" not in sys.argv)
    except CollectError as exc:
        print(f"함수 추출 실패: {exc}", file=sys.stderr)
        return 1

    out_path = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--json=")), None)
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(functions, ensure_ascii=False, indent=2), encoding="utf-8")

    tests = sum(1 for f in functions if f["is_test"])
    docs = sum(1 for f in functions if f["docstring"])
    print(f"함수 {len(functions)}개 "
          f"(테스트 {tests} / 독스트링 있음 {docs} / 파일 {len({f['file'] for f in functions})}개)")
    for f in functions[:5]:
        print(f"  {f['file']}:{f['start_line']}  {f['signature'][:70]}  (commits {f['commit_count']})")
    if out_path:
        print(f"저장: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
