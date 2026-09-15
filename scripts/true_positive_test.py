"""PHASE 1 사전 검증 — 리콜 측정. 진짜 차이가 있는 쌍을 주고 잡아내는지 본다.

make_samples.py 가 뽑는 쌍은 정답이 SKIP인 경우가 대부분이라 정밀도만 측정된다.
여기서는 **사람이 코드로 직접 확인한 실제 차이**만 골라 리콜을 잰다.
CASES 는 검증 저장소를 바꿀 때마다 사람이 손으로 채워야 한다.

`--strip-docstrings` 를 주면 독스트링을 지우고 묻는다.
모델이 "문서화된 의도이므로 물어볼 필요 없다"며 SKIP하는지 분리해 보기 위한 대조군이다.

사용법:
    py -m scripts.true_positive_test repos/psf__requests cache/결정적테스트.txt
    py -m scripts.true_positive_test <clone경로> <출력> --strip-docstrings
"""

import ast
import json
import sys
import time
from pathlib import Path

from scripts.make_samples import PROMPT_HEAD
from scripts.run_validation import DEFAULT_MODEL, REPO_ROOT, ask, make_client

# (파일A, 함수A, 파일B, 함수B, 사람이 코드로 확인한 진짜 차이)
# 같은 저장소 안에서 같은 이름이 여러 파일에 override로 흩어져 있는 경우를 함께 다루기 위해
# A/B의 파일 경로를 분리해 받는다. 같은 파일 안 두 함수를 쓰려면 파일A==파일B 로 두면 된다.
# 검증 저장소를 바꿀 때마다 사람이 손으로 채운다.
CASES = [
    ("mhctools/base_predictor.py", "predict_with_flanks",
     "mhctools/mhcflurry.py", "predict_with_flanks",
     "base_predictor.predict_with_flanks 는 _check_flank_inputs 로 검증만 하고 "
     "flanks 를 버린 채 self.predict(peptide_list) 를 부른다 (기본 구현이 flanks 무시). "
     "mhcflurry override 는 n_flanks=..., c_flanks=... 를 그대로 self.predict 에 넘겨 사용한다."),
    ("mhctools/calis.py", "_check_peptides",
     "mhctools/eramer.py", "_check_peptides",
     "eramer._check_peptides 는 min-max 길이 검증 위에 'n <= self.epitope_length 면 에러' "
     "라는 조건이 하나 더 있다. calis._check_peptides 에는 이 조건이 없다."),
    ("mhctools/caphla.py", "_check_peptides",
     "mhctools/deepimmuno.py", "_check_peptides",
     "caphla._check_peptides 는 length 체크 뒤 AA 유효성(_AMINO_ACIDS[:-1]) 을 검증한다. "
     "deepimmuno._check_peptides 는 length 만 검증하고 AA 유효성 검증이 없다."),
]


def get_func(repo: Path, rel: str, name: str, strip_docstring: bool) -> str:
    lines = (repo / rel).read_text(encoding="utf-8").splitlines()
    tree = ast.parse("\n".join(lines))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != name:
            continue

        body = lines[node.lineno - 1:node.end_lineno]
        if strip_docstring and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                a = first.lineno - node.lineno
                b = first.end_lineno - node.lineno
                body = body[:a] + body[b + 1:]
        return "\n".join(body)

    raise SystemExit(f"함수를 찾지 못함: {rel}:{name}")


def main() -> int:
    if len(sys.argv) < 3:
        print("사용법: py -m scripts.true_positive_test <clone경로> <출력파일> "
              "[모델] [--strip-docstrings]", file=sys.stderr)
        return 2

    repo = Path(sys.argv[1])
    repo = repo if repo.is_absolute() else REPO_ROOT / repo
    out_path = Path(sys.argv[2])
    out_path = out_path if out_path.is_absolute() else REPO_ROOT / out_path

    model = next((a for a in sys.argv[3:] if not a.startswith("--")), DEFAULT_MODEL)
    strip = "--strip-docstrings" in sys.argv

    client = make_client()
    print(f"모델 {model} / temperature 0 / 독스트링 {'제거' if strip else '유지'}\n")

    out = [f"# 리콜 측정 — 진짜 차이가 있는 쌍 {len(CASES)}개\n",
           f"# 모델 {model}, 독스트링 {'제거' if strip else '유지'}\n"]
    caught = 0

    for i, (rel_a, a_name, rel_b, b_name, truth) in enumerate(CASES):
        a_src = get_func(repo, rel_a, a_name, strip)
        b_src = get_func(repo, rel_b, b_name, strip)
        prompt = (f"{PROMPT_HEAD}\n\n--- 함수 A ---\n파일: {rel_a}\n함수명: {a_name}\n"
                  f"```python\n{a_src}\n```\n\n--- 함수 B ---\n파일: {rel_b}\n함수명: {b_name}\n"
                  f"```python\n{b_src}\n```\n")

        if i:
            time.sleep(7)
        text, err = ask(client, model, prompt)

        if err:
            verdict, summary = "ERROR", err
        else:
            data = json.loads(text)
            verdict = "KEEP" if data.get("keep") else "SKIP"
            summary = data.get("summary") or data.get("reason") or ""
            caught += bool(data.get("keep"))

        label = f"{rel_a.split('/')[-1]}:{a_name} <-> {rel_b.split('/')[-1]}:{b_name}"
        print(f"  [T{i + 1}] {label}")
        print(f"        진짜 차이: {truth}")
        print(f"        결과: {verdict}, {summary[:88]}\n")

        out.append(f"\n{'=' * 78}\n[T{i + 1}] {label}  ->  {verdict}\n"
                   f"{'=' * 78}\n")
        out.append(f"[사람이 확인한 진짜 차이]\n{truth}\n\n[모델 응답]\n{text or err}\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(out), encoding="utf-8")

    print(f"진짜 차이 {len(CASES)}개 중 잡아낸 것: {caught}")
    print(f"결과 저장: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
