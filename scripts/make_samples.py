"""PHASE 1 사전 검증 — 함수 쌍 샘플을 뽑아 프롬프트 파일로 만든다.

13.2절 샘플 수집(유사 10 + 일관성 10 + negative 5)과 13.3절 프롬프트를 구현한다.
제품 코드가 아니라 검증 도구다. analyzer/ · judge/ 와 섞지 않는다.

사용법:
    py -m scripts.make_samples repos/psf__requests cache/검증샘플25.txt
"""

import ast
import itertools
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 55   # 붙여넣기 가능한 길이로 제한
MIN_LINES = 4

# 쌍 비교가 O(n^2)라 함수 수에 상한을 둔다. 250개면 약 3만 쌍으로 수십 초 안에 끝난다.
# 초과하면 파일 경로 순으로 앞에서부터 자른다.
MAX_FUNCS = 250

# 13.3절이 정한 프롬프트. true_positive_test.py 도 이 상수를 가져다 쓴다.
PROMPT_HEAD = """너는 낯선 저장소를 넘겨받은 개발자를 돕는 분석기다.
같은 저장소에서 뽑은 함수 두 개를 보고, 다음 개발자가 이전 개발자에게
물어봐야 할 것이 있는지 판단한다.

규칙:
1. 작성자의 실제 의도를 단정하지 마라.
2. 코드에서 직접 확인 가능한 사실과 추론을 구분하라.
3. 차이가 다음 개발자가 확인할 가치가 있을 때만 finding을 생성하라.
4. finding을 생성하면 반드시 근거와 질문을 함께 반환하라.
5. 가치가 없으면 SKIP을 반환하라.

확인할 가치가 있으면 이 JSON만 출력한다:
{
  "keep": true,
  "category": "similar_logic_difference",
  "summary": "한 줄 요약",
  "why_clarify": "코드에서 확인되는 사실만 근거로 쓴다",
  "question": "이전 개발자에게 물어볼 구체적인 질문 한 개",
  "evidence": [
    {"file": "경로", "line": 0},
    {"file": "경로", "line": 0}
  ],
  "confidence": 0.0
}

가치가 없으면 이 JSON만 출력한다:
{"keep": false, "category": "skip", "reason": "이유"}

다른 말은 덧붙이지 않는다.
"""

EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                "build", "dist", "vendor", "third_party", "docs", "examples"}


def is_test_file(rel: Path) -> bool:
    """테스트 파일은 비교 대상에서 뺀다. 인수인계에서 물어볼 대상은 production 코드다."""
    return (rel.name.startswith("test_") or rel.name.endswith("_test.py")
            or any(p in ("test", "tests") for p in rel.parts[:-1])
            or rel.name in ("setup.py", "conftest.py"))


def normalize(src: str) -> str:
    """비교용 정규화 — 독스트링/주석/공백 제거."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"#.*", "", src)
    return re.sub(r"\s+", " ", src).strip()


def load_functions(repo: Path) -> list[dict]:
    funcs = []
    for path in sorted(repo.rglob("*.py")):
        rel = path.relative_to(repo)
        if not EXCLUDE_DIRS.isdisjoint(rel.parts) or is_test_file(rel):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            length = node.end_lineno - node.lineno + 1
            if not MIN_LINES <= length <= MAX_LINES:
                continue
            src = "\n".join(lines[node.lineno - 1:node.end_lineno])
            funcs.append({"file": rel.as_posix(), "name": node.name,
                          "line": node.lineno, "source": src, "norm": normalize(src)})

    if len(funcs) > MAX_FUNCS:
        print(f"함수 {len(funcs)}개 중 앞 {MAX_FUNCS}개만 사용합니다 (쌍 비교가 O(n^2)).")
        funcs = funcs[:MAX_FUNCS]
    return funcs


def pick(funcs: list[dict]):
    """유사 10 / 일관성 10 / negative 5 를 겹치지 않게 고른다(13.2절)."""
    pairs = [(a, b, SequenceMatcher(None, a["norm"], b["norm"]).ratio())
             for a, b in itertools.combinations(funcs, 2)]

    # 한 함수는 전체에서 한 번만 쓴다. 버킷끼리 같은 쌍이 겹치는 것을 막는다.
    used: set[tuple[str, str]] = set()

    # 일관성 차이를 먼저 고른다 — 같은 이름이 두 곳에 있는 쌍이 가장 값지다.
    consistency = take(
        sorted((p for p in pairs
                if (p[0]["name"] == p[1]["name"] and p[0]["file"] != p[1]["file"])
                or (p[0]["file"] == p[1]["file"] and p[2] >= 0.45
                    and p[0]["name"] != p[1]["name"])),
               key=lambda p: (p[0]["name"] != p[1]["name"], -p[2])),
        10, used, max_per_filepair=3)

    similar = take(
        sorted((p for p in pairs if 0.55 <= p[2] <= 0.93 and p[0]["name"] != p[1]["name"]),
               key=lambda p: (p[0]["file"] == p[1]["file"], -p[2])),
        10, used, max_per_filepair=3)

    negative = take(sorted((p for p in pairs if p[2] < 0.18), key=lambda p: p[2]),
                    5, used, max_per_filepair=1)

    return similar, consistency, negative


def take(pairs, want, used, max_per_filepair=99):
    """이미 쓴 함수를 피하고, 같은 파일 조합에 쏠리지 않게 고른다."""
    out, filepairs = [], {}
    for a, b, r in pairs:
        ka, kb = (a["file"], a["name"]), (b["file"], b["name"])
        if ka in used or kb in used:
            continue
        fp = tuple(sorted((a["file"], b["file"])))
        if filepairs.get(fp, 0) >= max_per_filepair:
            continue
        used.update((ka, kb))
        filepairs[fp] = filepairs.get(fp, 0) + 1
        out.append((a, b, r))
        if len(out) == want:
            break
    return out


def render(idx: int, kind: str, a: dict, b: dict, r: float) -> str:
    bar = "=" * 78
    return f"""
{bar}
[{idx:02d}] {kind}   (참고: 코드 유사도 {r:.2f} — LLM에는 주지 않는다)
{bar}

{PROMPT_HEAD}
--- 함수 A ---
파일: {a["file"]}
함수명: {a["name"]}
```python
{a["source"]}
```

--- 함수 B ---
파일: {b["file"]}
함수명: {b["name"]}
```python
{b["source"]}
```
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("사용법: py -m scripts.make_samples <clone경로> <출력파일>", file=sys.stderr)
        return 2

    repo = Path(sys.argv[1])
    if not repo.is_absolute():
        repo = REPO_ROOT / repo
    if not repo.is_dir():
        print(f"저장소 경로가 없습니다: {repo}", file=sys.stderr)
        return 1

    funcs = load_functions(repo)
    similar, consistency, negative = pick(funcs)

    out = ["# Re:Code PHASE 1 사전 검증 샘플\n",
           f"# 출처: {repo.name} (함수 {len(funcs)}개에서 선별)\n",
           "# '참고:' 줄은 사람용 메모다. run_validation.py 가 프롬프트에서 제거한다.\n"]

    idx, listing = 1, []
    for kind, pairs in (("유사 함수 쌍", similar),
                        ("일관성 차이 후보", consistency),
                        ("negative (SKIP이 나와야 정상)", negative)):
        for a, b, r in pairs:
            out.append(render(idx, kind, a, b, r))
            listing.append(f"  [{idx:02d}] {kind[:9]:9s} {a['file'].split('/')[-1]}:{a['name']}"
                           f"  <->  {b['file'].split('/')[-1]}:{b['name']}   ({r:.2f})")
            idx += 1

    out_path = Path(sys.argv[2])
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(out), encoding="utf-8")

    print(f"함수 {len(funcs)}개 -> 쌍 {idx - 1}개 "
          f"(유사 {len(similar)} / 일관성 {len(consistency)} / negative {len(negative)})")
    print("\n".join(listing))
    print(f"\n저장: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
