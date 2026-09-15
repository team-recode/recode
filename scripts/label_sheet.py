"""PHASE 9 — finding 을 사람이 라벨링할 시트로 바꾸고, 채운 시트를 집계한다(21절).

21절은 각 finding 을 useful / ambiguous / not useful 로 사람이 직접 라벨링하라고 한다.
자동 채점이 아니다. 이 스크립트는 채점표를 만들고 세기만 한다.

만들기:
    py -m scripts.label_sheet make outputs/psf__requests/findings.json 라벨_requests.txt

집계 (라벨을 채운 뒤):
    py -m scripts.label_sheet count 라벨_requests.txt
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELS = ("useful", "ambiguous", "not_useful")

# "라벨: useful" 처럼 적힌 줄을 읽는다. 대소문자와 공백은 무시한다.
# 가로 공백만 건너뛴다. \s* 를 쓰면 빈 "라벨:" 에서 줄바꿈을 넘어가 다음 줄을 값으로 읽는다.
LABEL_RE = re.compile(r"^라벨:[^\S\n]*(\S+)[^\S\n]*$", re.MULTILINE)


def resolve(arg: str) -> Path:
    path = Path(arg)
    return path if path.is_absolute() else REPO_ROOT / path


def make(findings_path: Path, out_path: Path) -> int:
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    if not findings:
        print(f"finding 이 0건입니다: {findings_path}", file=sys.stderr)
        return 1

    lines = [
        f"# PHASE 9 사람 평가 — {findings_path.parent.name}",
        f"# finding {len(findings)}건. 각 항목의 '라벨:' 뒤에 셋 중 하나를 적는다.",
        f"#   {' / '.join(LABELS)}",
        "# 오탐이면 '메모:' 에 왜 그런지 한 줄 남긴다. 그 메모가 프롬프트 개선 재료가 된다.",
        "",
    ]

    for i, f in enumerate(findings, 1):
        evidence = ", ".join(f"{e['file']}:{e['line']}" for e in f["evidence"])
        lines += [
            "=" * 78,
            f"[{i:02d}] confidence {f['confidence']}  (유사도 {f['pair'].get('similarity')})",
            f"     {f['pair']['a']}",
            f"     {f['pair']['b']}",
            "=" * 78,
            "",
            f"요약   : {f['summary']}",
            f"질문   : {f['question']}",
            f"확인사실: {f['why_clarify']}",
            f"근거   : {evidence}",
        ]
        if f.get("also_seen"):
            lines.append(f"같은패턴: {len(f['also_seen'])}곳 더")
        lines += ["", "라벨: ", "메모: ", ""]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"라벨 시트 생성: {out_path} (finding {len(findings)}건)")
    print(f"각 항목의 '라벨:' 뒤에 {' / '.join(LABELS)} 중 하나를 적으세요.")
    return 0


def count(sheet_path: Path) -> int:
    text = sheet_path.read_text(encoding="utf-8")
    total = text.count("\n라벨:")
    filled = {label: 0 for label in LABELS}
    unknown = []

    for raw in LABEL_RE.findall(text):
        key = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if key in filled:
            filled[key] += 1
        else:
            unknown.append(raw)

    labeled = sum(filled.values())
    print(f"라벨 {labeled}/{total}건 기입됨")
    for label in LABELS:
        share = f"{filled[label] / labeled * 100:.0f}%" if labeled else "-"
        print(f"  {label:11s} {filled[label]:3d}  {share}")

    if unknown:
        print(f"\n알 수 없는 값 {len(unknown)}건: {', '.join(sorted(set(unknown))[:5])}")
    if labeled < total:
        print(f"\n아직 {total - labeled}건이 비어 있습니다.")
    elif labeled:
        # 21절 목표 수치 중 하나. 샘플이 작으므로 "내부 검증"으로 표기할 것.
        # 화면에 나가는 문자열에는 em-dash 를 쓰지 않는다. Windows cp949 콘솔에서 인코딩 오류가 난다.
        print(f"\n유용 finding 비율: {filled['useful'] / labeled * 100:.0f}% "
              f"(useful {filled['useful']} / 전체 {labeled}), 내부 검증(n={labeled})")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("make", "count"):
        print("사용법:\n"
              "  py -m scripts.label_sheet make <findings.json> <출력.txt>\n"
              "  py -m scripts.label_sheet count <라벨시트.txt>", file=sys.stderr)
        return 2

    if args[0] == "make":
        if len(args) != 3:
            print("make 는 인자 2개가 필요합니다.", file=sys.stderr)
            return 2
        return make(resolve(args[1]), resolve(args[2]))

    return count(resolve(args[1]))


if __name__ == "__main__":
    sys.exit(main())
