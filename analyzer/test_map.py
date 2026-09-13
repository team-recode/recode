"""PHASE 4 — 16.3 Test Evidence Gap.

테스트 파일의 import를 역추적해 production 파일과 연결한다.
연결이 없다는 것은 "테스트가 없다"가 아니라 "직접 연결된 근거를 찾지 못했다"는 뜻이다.

사용법:
    py -m analyzer.test_map repos/psf__requests
"""

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

from analyzer.collect import CollectError, _git
from analyzer.static_check import EXCLUDE_DIRS, iter_python_files

# 근거의 한계를 그대로 드러내는 문구. "테스트 없음"이라고 쓰지 않는다(16.3 / 10.2 ④).
NO_TEST_EVIDENCE_MESSAGE = "직접 연결된 테스트 근거를 찾지 못했습니다."

# import 경로의 기준이 되는 디렉터리. src 레이아웃이면 src/requests/models.py → requests.models.
SOURCE_ROOTS = ("", "src")


def is_test_file(rel_path: Path) -> bool:
    """tests/ 아래이거나 test_*.py / *_test.py 이면 테스트 파일로 본다(16.3)."""
    name = rel_path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(part in ("test", "tests") for part in rel_path.parts[:-1])


def _module_names(rel_path: Path) -> list[str]:
    """production 파일이 가질 수 있는 모듈 이름들을 돌려준다."""
    names = []
    for root in SOURCE_ROOTS:
        parts = rel_path.parts
        if root:
            if len(parts) < 2 or parts[0] != root:
                continue
            parts = parts[1:]
        stem = parts[:-1] if parts[-1] == "__init__.py" else (*parts[:-1], parts[-1][:-3])
        if stem:
            names.append(".".join(stem))
    return names


def _imported_modules(test_path: Path, rel_path: Path) -> set[str]:
    """테스트 파일이 import하는 모듈 이름을 ast로 뽑는다."""
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        # 파싱 못 한 파일은 근거로 쓸 수 없다. 추측하지 않고 건너뛴다.
        return set()

    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # 상대 import는 테스트 파일이 속한 패키지를 기준으로 되돌린다.
                package = list(rel_path.parts[:-1])
                package = package[: len(package) - node.level + 1]
                base = ".".join(filter(None, [*package, base]))
            if base:
                modules.add(base)
                # from pkg.mod import name — name 자체가 모듈일 수 있다.
                modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


def _commit_counts(clone_path: Path) -> dict[str, int]:
    """파일별 전체 커밋 수를 git 이력 한 번으로 센다."""
    log = _git(["log", "--pretty=format:", "--name-only"], cwd=clone_path, timeout=120)
    counts = defaultdict(int)
    for line in log.splitlines():
        if line.endswith(".py") and EXCLUDE_DIRS.isdisjoint(Path(line).parts):
            counts[line] += 1
    return counts


def test_evidence_gap(clone_path: Path) -> list[dict]:
    """production 파일별로 직접 연결된 테스트를 찾아 돌려준다(16.3).

    변경이 잦은 파일이 앞에 오도록 정렬한다 — `high churn + no direct test evidence`
    조합이 가장 먼저 눈에 들어와야 한다.
    """
    if not (clone_path / ".git").is_dir():
        raise CollectError(f"git 저장소가 아닙니다: {clone_path}")

    production, tests = {}, []
    for path in iter_python_files(clone_path):
        rel_path = path.relative_to(clone_path)
        if is_test_file(rel_path):
            tests.append((path, rel_path))
        else:
            production[rel_path.as_posix()] = _module_names(rel_path)

    # 모듈 이름 → production 파일 역색인
    by_module = defaultdict(set)
    for file, names in production.items():
        for name in names:
            by_module[name].add(file)

    related = defaultdict(set)
    for test_path, test_rel in tests:
        test_file = test_rel.as_posix()
        for module in _imported_modules(test_path, test_rel):
            for file in by_module.get(module, ()):
                related[file].add(test_file)

    counts = _commit_counts(clone_path)
    results = []
    for file in production:
        linked = sorted(related.get(file, ()))
        row = {
            "file": file,
            "related_tests": linked,
            "commit_count": counts.get(file, 0),
        }
        if not linked:
            row["message"] = NO_TEST_EVIDENCE_MESSAGE
        results.append(row)

    results.sort(key=lambda row: (bool(row["related_tests"]), -row["commit_count"], row["file"]))
    return results


def main() -> int:
    if len(sys.argv) != 2:
        print("사용법: py -m analyzer.test_map repos/owner__repo", file=sys.stderr)
        return 2

    try:
        rows = test_evidence_gap(Path(sys.argv[1]))
    except CollectError as exc:
        print(f"테스트 연결 분석 실패: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
