"""PHASE 7 — HANDOFF.md 생성(19절).

analyzer/(③④⑥ 정적 evidence)와 judge/llm.py(①② finding)를 합쳐 인수인계 문서를 만든다.

19절 출력 원칙을 코드로 강제한다:
- 결과 0건인 섹션은 숨긴다
- 모든 finding 에 Evidence 가 있어야 한다
- 경고 개수를 부풀리지 않는다
- 같은 근거를 여러 섹션에서 중복 출력하지 않는다
- 질문은 최대 10개
- 첫 주 할 일은 최대 3개

사용법:
    py -m judge.report repos/openvax__mhctools cache/mhctools_findings.json
    py -m judge.report <clone> <findings.json> --out=HANDOFF.md
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from analyzer.collect import CollectError, _git
from analyzer.static_check import dead_code, high_churn
from analyzer.test_map import is_test_file, test_evidence_gap

MAX_QUESTIONS = 10          # 19절: 질문은 최대 5~10개
MAX_FIRST_WEEK = 3          # 19절: 첫 주 할 일은 최대 3개
MAX_BEFORE_YOU_TOUCH = 5
MAX_LIST_ROWS = 10          # 근거 목록이 길어져 개수가 부풀어 보이지 않게 한다


def _overview(clone_path: Path) -> dict:
    return {
        "name": clone_path.name.replace("__", "/"),
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=clone_path),
        "head_sha": _git(["rev-parse", "--short", "HEAD"], cwd=clone_path),
        "commit_count": int(_git(["rev-list", "--count", "HEAD"], cwd=clone_path)),
    }


def group_findings(findings: list[dict]) -> list[dict]:
    """같은 함수 쌍에 대한 finding 을 하나로 묶는다.

    18절의 중복 제거는 질문 텍스트 완전일치라 의미가 같고 문장만 다른 질문을 못 잡는다.
    실측에서 finding 5건 중 3건이 같은 주제(기본 mode 차이)를 파일만 바꿔 반복했다.
    개수를 부풀리지 않기 위해 여기서 묶는다(19절).
    """
    groups: dict = defaultdict(list)
    for f in findings:
        a, b = f["pair"]["a"].rsplit(":", 1)[-1], f["pair"]["b"].rsplit(":", 1)[-1]
        groups[tuple(sorted((a, b)))].append(f)

    merged = []
    for items in groups.values():
        items.sort(key=lambda f: -f["confidence"])
        head = dict(items[0])
        head["also_seen"] = [f["pair"] for f in items[1:]]
        merged.append(head)

    merged.sort(key=lambda f: (-f["confidence"], f["summary"]))
    return merged


def _evidence_line(ev: list[dict]) -> str:
    return ", ".join(f"`{e['file']}:{e['line']}`" for e in ev)


def gather_evidence(clone_path: Path, findings: list[dict]) -> dict:
    """보고서에 쓸 근거를 한 번에 모은다.

    `build()`(마크다운)와 웹 화면(PHASE 11 Jinja2 템플릿)이 같은 데이터를 쓴다.
    두 곳에서 각자 계산하면 문서와 화면이 어긋난다.
    """
    if not (clone_path / ".git").is_dir():
        raise CollectError(f"git 저장소가 아닙니다: {clone_path}")

    # analyzer 는 16절대로 테스트 파일을 포함해 모든 근거를 낸다.
    # 인수인계 문서에서 물어볼 대상은 앞으로 고칠 production 코드이므로 여기서 거른다.
    # 거르지 않으면 dead-code 후보 55건 중 45건이 테스트의 미사용 변수로 채워져
    # "경고 개수를 부풀리지 않는다"(19절)에 어긋난다.
    churn = [r for r in high_churn(clone_path) if not is_test_file(Path(r["file"]))]
    dead = [d for d in dead_code(clone_path) if not is_test_file(Path(d["file"]))]
    gaps = [row for row in test_evidence_gap(clone_path) if not row["related_tests"]]

    churn_by_file = {r["file"]: r for r in churn}

    # 19절 First Week 1순위: high-churn + test evidence gap
    combined = sorted((row for row in gaps if row["file"] in churn_by_file),
                      key=lambda row: -row["commit_count"])[:MAX_BEFORE_YOU_TOUCH]
    for row in combined:
        row["commits_60d"] = churn_by_file[row["file"]]["commits_60d"]
        row["last_changed"] = churn_by_file[row["file"]]["last_changed"]

    grouped = group_findings(findings)

    # 19절 First Week 우선순위: high-churn+test gap -> consistency -> dead-code. 최대 3개.
    week = []
    if combined:
        week.append(f"`{combined[0]['file']}` 의 변경 이력을 읽고, "
                    "연결된 테스트가 정말 없는지 확인한다 (최근 60일 최다 변경 + 테스트 근거 없음)")
    if grouped:
        week.append(f"이전 개발자에게 물어볼 것: {grouped[0]['question']}")
    if dead:
        week.append(f"`{dead[0]['file']}:{dead[0]['line']}` 의 `{dead[0]['name']}` 이 "
                    "실제로 쓰이지 않는지 확인한다 (정적 분석으로는 호출 근거를 찾지 못함)")

    return {
        "overview": _overview(clone_path),
        "churn": churn,
        "dead": dead,
        "gaps": gaps,
        "findings": grouped,
        "before_you_touch": combined,
        "first_week": week[:MAX_FIRST_WEEK],
        "max_rows": MAX_LIST_ROWS,
        "max_questions": MAX_QUESTIONS,
    }


def build(clone_path: Path, findings: list[dict]) -> str:
    """HANDOFF.md 본문을 만든다."""
    data = gather_evidence(clone_path, findings)
    overview = data["overview"]
    churn, dead, gaps = data["churn"], data["dead"], data["gaps"]
    grouped, combined = data["findings"], data["before_you_touch"]
    combined_files = {row["file"] for row in combined}

    out = ["# Re:Code Handoff", ""]
    out += [f"> `{overview['name']}` · {overview['branch']} · "
            f"`{overview['head_sha']}` · 커밋 {overview['commit_count']}개", ""]
    out += ["이 문서는 코드를 설명하지 않는다. **수정 전에 확인해야 할 것**만 모았다.",
            "모든 항목에는 코드 근거가 붙어 있다. 근거가 없는 항목은 만들지 않았다.", ""]

    out += ["## 1. Repository overview", "",
            f"- 저장소: `{overview['name']}`",
            f"- 기준 커밋: `{overview['head_sha']}` (`{overview['branch']}`)",
            f"- 전체 커밋: {overview['commit_count']}개", ""]

    # 2. Before you touch this repo — 가장 강한 조합만. 나머지 섹션과 중복시키지 않는다.
    if combined:
        out += ["## 2. Before you touch this repo", ""]
        for i, row in enumerate(combined, 1):
            out += [f"### {i}. `{row['file']}`", "",
                    "Evidence:",
                    f"- 최근 60일간 {row['commits_60d']}회 변경 "
                    f"(마지막 {row['last_changed']})",
                    f"- {row['message']}", "",
                    "Why this matters:",
                    "- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. "
                    "수정 시 회귀를 잡아줄 장치를 먼저 확인할 것", ""]

    # 3. Questions — ①② finding
    if grouped:
        out += ["## 3. Questions for the previous developer", ""]
        for i, f in enumerate(grouped[:MAX_QUESTIONS], 1):
            out += [f"{i}. {f['question']}",
                    f"   - 근거: {_evidence_line(f['evidence'])}",
                    f"   - 확인된 사실: {f['why_clarify']}"]
            if f["also_seen"]:
                # 개수를 부풀리지 않되, 같은 패턴이 더 있다는 사실은 숨기지 않는다.
                where = ", ".join(f"`{p['a']}` ↔ `{p['b']}`" for p in f["also_seen"][:3])
                out += [f"   - 같은 패턴이 {len(f['also_seen'])}곳에서 더 보인다: {where}"]
            out += [""]

    # 4. High-change areas — 2번에 이미 나온 파일은 뺀다(근거 중복 금지)
    rest_churn = [r for r in churn if r["file"] not in combined_files]
    if rest_churn:
        out += ["## 4. High-change areas", "",
                "최근 60일간 반복적으로 변경된 영역이다. 변경 횟수는 git 이력에서 센 수치다.", "",
                "| 파일 | 60일 변경 | 마지막 변경 |", "|---|---|---|"]
        out += [f"| `{r['file']}` | {r['commits_60d']} | {r['last_changed']} |"
                for r in rest_churn[:MAX_LIST_ROWS]]
        if len(rest_churn) > MAX_LIST_ROWS:
            out += [f"", f"그 외 {len(rest_churn) - MAX_LIST_ROWS}개 파일."]
        out += [""]

    # 5. Test evidence gaps — 2번에 이미 나온 파일은 뺀다
    rest_gaps = [r for r in gaps if r["file"] not in combined_files]
    if rest_gaps:
        out += ["## 5. Test evidence gaps", "",
                f"{rest_gaps[0]['message']} 테스트가 없다는 뜻은 아니다.", "",
                "| 파일 | 전체 커밋 |", "|---|---|"]
        out += [f"| `{r['file']}` | {r['commit_count']} |" for r in rest_gaps[:MAX_LIST_ROWS]]
        if len(rest_gaps) > MAX_LIST_ROWS:
            out += [f"", f"그 외 {len(rest_gaps) - MAX_LIST_ROWS}개 파일."]
        out += [""]

    # 6. Dead-code candidates — 삭제 권고가 아니라 확인 후보다
    if dead:
        out += ["## 6. Dead-code candidates", "",
                f"{dead[0]['message']} 삭제를 권하는 것이 아니라 확인이 필요한 후보다.", "",
                "| 위치 | 이름 | 종류 | confidence |", "|---|---|---|---|"]
        out += [f"| `{d['file']}:{d['line']}` | `{d['name']}` | {d['kind']} | {d['confidence']}% |"
                for d in dead[:MAX_LIST_ROWS]]
        if len(dead) > MAX_LIST_ROWS:
            out += [f"", f"그 외 {len(dead) - MAX_LIST_ROWS}개 후보."]
        out += [""]

    # 7. First week — 19절 우선순위. gather_evidence 가 이미 3개로 잘라 준다.
    week = data["first_week"]
    if week:
        out += ["## 7. First week", ""]
        out += [f"{i}. {item}" for i, item in enumerate(week, 1)]
        out += [""]

    return "\n".join(out)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print("사용법: py -m judge.report <clone경로> <findings.json> [--out=HANDOFF.md]",
              file=sys.stderr)
        return 2

    clone_path = Path(args[0])
    findings = json.loads(Path(args[1]).read_text(encoding="utf-8"))

    try:
        text = build(clone_path, findings)
    except CollectError as exc:
        print(f"보고서 생성 실패: {exc}", file=sys.stderr)
        return 1

    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), None)
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        sections = text.count("\n## ")
        print(f"HANDOFF 생성: {out} ({len(text.splitlines())}줄 / 섹션 {sections}개)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
