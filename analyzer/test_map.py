"""PHASE 4 — 16.3 Test Evidence Gap.

테스트 파일의 import를 역추적해 production 파일과 연결한다.
연결이 없다는 것은 "테스트가 없다"가 아니라 "직접 연결된 근거를 찾지 못했다"는 뜻이다.

사용법:
    py -m analyzer.test_map repos/psf__requests
"""

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from analyzer.collect import CollectError, _git
from analyzer.static_check import EXCLUDE_DIRS, iter_python_files
from judge import languages

# 근거의 한계를 그대로 드러내는 문구. "테스트 없음"이라고 쓰지 않는다(16.3 / 10.2 ④).
NO_TEST_EVIDENCE_MESSAGE = "직접 연결된 테스트 근거를 찾지 못했습니다."

# import 경로의 기준이 되는 디렉터리. src 레이아웃이면 src/requests/models.py → requests.models.
SOURCE_ROOTS = ("", "src")


def is_test_file(rel_path: Path) -> bool:
    """tests/ 아래이거나 test_*.py / *_test.py 이면 테스트 파일로 본다(16.3)."""
    # 같은 파일을 여기서는 테스트로, 다른 파일에서는 아니라고 보던 불일치가 있었다
    # (PHASE 12 자기참조 분석에서 실제로 걸렸다). 판단은 languages 한 곳에서만 한다.
    return languages.is_test_file(rel_path)


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


# 테스트 파일 이름에서 떼어내면 대상 파일 이름이 되는 조각들.
# `FooTest.java` -> `Foo`, `foo.test.ts` -> `foo`, `test_foo.c` -> `foo`
TEST_AFFIX_RE = [
    re.compile(r"\.(test|spec)$", re.IGNORECASE),
    re.compile(r"^test_"),
    re.compile(r"_test$"),
    re.compile(r"^Test(?=[A-Z])"),
    re.compile(r"Tests?$"),
]


def _target_stems(test_rel: Path) -> set[str]:
    """이 테스트 파일이 검사할 법한 대상 파일의 이름(확장자 제외) 후보."""
    stem = test_rel.name
    for _ in range(2):                       # `foo.test.ts` 처럼 두 겹인 경우가 있다
        stem = Path(stem).stem
        if "." not in stem:
            break
    stems = {stem}
    for pattern in TEST_AFFIX_RE:
        stripped = pattern.sub("", stem)
        if stripped and stripped != stem:
            stems.add(stripped)
    return {s for s in stems if len(s) > 2}   # 두 글자 이름은 우연히 겹친다


def evidence_by_convention(clone_path: Path) -> dict[str, list[str]]:
    """Python 외 언어에서 테스트와 production 파일을 잇는다(16.3).

    Python 은 `ast` 로 import 를 역추적하지만 다른 언어는 그 방법이 안 통한다.
    대신 두 가지 근거를 쓴다. 둘 다 코드에서 직접 확인되는 사실이다.
      1. 이름 규칙 — `FooTest.java` 는 `Foo.java` 를, `foo.spec.ts` 는 `foo.ts` 를 검사한다
      2. 식별자 참조 — 테스트 파일 안에 대상 파일 이름이 식별자로 등장한다
    둘 중 하나라도 맞으면 "직접 연결된 근거" 로 본다. 못 찾아도 "테스트가 없다" 가 아니다.
    """
    production: dict[str, str] = {}          # stem -> 파일 경로
    tests: list[tuple[str, Path, object]] = []

    for path, rel, lang in languages.iter_source_files(clone_path):
        if lang.grammar is None or not lang.analyzable:
            continue                         # Python 은 import 역추적 쪽이 담당한다
        if languages.is_test_file(rel):
            tests.append((rel, path, lang))
        else:
            production.setdefault(Path(rel).stem, rel)

    related: dict[str, set[str]] = defaultdict(set)
    for rel, path, lang in tests:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            names = set(languages.identifier_counts(text, lang))
        except Exception:                    # noqa: BLE001
            names = set()

        for stem in _target_stems(Path(rel)):
            if stem in production:
                related[production[stem]].add(rel)
        # 이름 규칙이 안 맞아도 테스트가 대상 이름을 직접 부르면 근거가 된다.
        for stem, prod_rel in production.items():
            if stem in names:
                related[prod_rel].add(rel)

    return {file: sorted(rels) for file, rels in related.items()}


def commit_counts(clone_path: Path) -> dict[str, int]:
    """파일별 전체 커밋 수를 git 이력 한 번으로 센다.

    지원 언어를 전부 센다. `.py` 만 세면 `judge/extract.py` 가 이 값으로 파일을 정렬할 때
    Java · TypeScript 파일이 모두 0이 되어, 상한 2,000개에 걸릴 때 손이 자주 닿은
    코드가 아니라 경로 이름 순으로 남는다.
    """
    log = _git(["log", "--pretty=format:", "--name-only"], cwd=clone_path, timeout=120)
    counts = defaultdict(int)
    for line in log.splitlines():
        if line and languages.detect(line) is not None and not languages.is_excluded(line):
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

    # Python 외 언어는 이름 규칙과 식별자 참조로 잇는다.
    by_convention = evidence_by_convention(clone_path)
    for file, rels in by_convention.items():
        related[file].update(rels)
    # production 목록에도 다른 언어 파일을 넣는다. 넣지 않으면 Java 파일은
    # 테스트가 있든 없든 이 섹션에 아예 나오지 않는다.
    for path, rel, lang in languages.iter_source_files(clone_path):
        if lang.grammar is not None and lang.analyzable and not is_test_file(Path(rel)):
            production.setdefault(rel, [])

    counts = commit_counts(clone_path)
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
