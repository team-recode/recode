"""PHASE 6 — LLM 판정(18절).

PHASE 5가 고른 후보 쌍을 LLM에 넘겨 finding을 만든다.
LLM은 정답 판정기가 아니다. 차이를 설명하고, 확인 가치를 판단하고, 질문을 만들고,
근거가 부족하면 SKIP한다.

프롬프트는 PHASE 1에서 검증된 것(`scripts/make_samples.PROMPT_HEAD`)을 출발점으로 하되
18절이 요구하는 강제 규칙을 추가했다. 검증 스크립트 쪽은 재현을 위해 원본을 유지하므로
두 프롬프트는 의도적으로 다르다.

사용법:
    py -m judge.llm repos/openvax__mhctools cache/mhctools_pairs.json
    py -m judge.llm <clone> <pairs.json> --model=gemini-3-flash-preview --limit=10
"""

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from analyzer.collect import CollectError

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
CACHE_DIR = REPO_ROOT / "cache" / "llm"

# gemini-3.6-flash 는 목록에서 사라졌다. 이 모델이 PHASE 1 2차 사이클에서 CASES 6/6 을 통과했다.
# quota 는 모델별로 독립이므로 소진되면 --model= 로 교체한다.
DEFAULT_MODEL = "gemini-3-flash-preview"

RETRIES = 2            # 18절 API 실패 대응: 1~2회 재시도
SPACING_SEC = 7        # 무료 티어 분당 요청 제한 대비 간격
QUOTA_BACKOFF = 65     # 429는 분 단위 창이 리셋될 때까지 기다린다
TIMEOUT_MS = 120_000   # 18절 timeout

# 18절: 낮은 confidence는 최종 문서에서 제외 가능
MIN_CONFIDENCE = 0.5

# 18절 강제 규칙을 담은 제품 프롬프트.
# 1~5번은 PHASE 1에서 검증된 원문 그대로다. 6~8번이 18절에서 추가된 규칙.
PROMPT = """너는 낯선 저장소를 넘겨받은 개발자를 돕는 분석기다.
같은 저장소에서 뽑은 함수 두 개를 보고, 다음 개발자가 이전 개발자에게
물어봐야 할 것이 있는지 판단한다.

규칙:
1. 작성자의 실제 의도를 단정하지 마라.
2. 코드에서 직접 확인 가능한 사실과 추론을 구분하라.
3. 차이가 다음 개발자가 확인할 가치가 있을 때만 finding을 생성하라.
4. finding을 생성하면 반드시 근거와 질문을 함께 반환하라.
5. 가치가 없으면 SKIP을 반환하라.
6. evidence 의 line 에는 아래 코드에 붙은 실제 줄 번호를 적어라. 0 을 쓰지 마라.
7. 코드가 AI로 생성되었다거나 그 때문에 생긴 문제라는 표현을 쓰지 마라.
8. 근거로 인용할 코드를 찾지 못하면 finding 을 만들지 말고 SKIP 하라.
9. 코드를 고치라고 제안하지 마라. 이 도구는 품질 검사기가 아니다.
   question 은 "왜 이렇게 되어 있는지" 를 이전 개발자에게 묻는 형태여야 한다.
   "~해야 하지 않나요", "~추가할 필요가 있습니까" 같은 개선 제안은 금지한다.
10. 동작에 영향이 없는 스타일 차이(따옴표, 공백, 줄바꿈, 이름 표기)만으로는
   finding 을 만들지 말고 SKIP 하라.

확인할 가치가 있으면 이 JSON만 출력한다:
{
  "keep": true,
  "category": "similar_logic_difference",
  "summary": "한 줄 요약",
  "why_clarify": "코드에서 확인되는 사실만 근거로 쓴다",
  "question": "이전 개발자에게 물어볼 구체적인 질문 한 개",
  "evidence": [
    {"file": "함수 A의 파일 경로", "line": 0},
    {"file": "함수 B의 파일 경로", "line": 0}
  ],
  "confidence": 0.0
}

가치가 없으면 이 JSON만 출력한다:
{"keep": false, "category": "skip", "reason": "이유"}

다른 말은 덧붙이지 않는다.
"""

# 18절: "AI가 생성해서 생긴 문제"라는 표현 금지. 규칙 7번이 새면 여기서 잡는다.
BANNED_PATTERNS = re.compile(r"(AI|인공지능|LLM|GPT|코파일럿|Copilot)[^.]{0,20}"
                             r"(생성|만들|작성)", re.IGNORECASE)


def numbered_source(clone_path: Path, side: dict) -> str:
    """함수 소스를 실제 줄 번호와 함께 돌려준다. evidence.line 을 0으로 뱉는 문제를 막는다."""
    lines = (clone_path / side["file"]).read_text(encoding="utf-8",
                                                  errors="replace").splitlines()
    start, end = side["start_line"], side["end_line"]
    return "\n".join(f"{n:5d} | {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))


def build_prompt(clone_path: Path, pair: dict) -> str:
    a, b = pair["a"], pair["b"]
    return (
        f"{PROMPT}\n"
        f"--- 함수 A ---\n파일: {a['file']}\n함수명: {a['name']}\n"
        f"```python\n{numbered_source(clone_path, a)}\n```\n\n"
        f"--- 함수 B ---\n파일: {b['file']}\n함수명: {b['name']}\n"
        f"```python\n{numbered_source(clone_path, b)}\n```\n"
    )


def validate(data: dict, pair: dict) -> tuple[dict | None, str | None]:
    """18절 강제 규칙을 적용한다. (finding, 버린 이유) 를 돌려준다."""
    if not data.get("keep"):
        return None, "skip"

    for field in ("summary", "why_clarify", "question"):
        if not str(data.get(field) or "").strip():
            return None, f"{field} 비어 있음"

    text = " ".join(str(data.get(f) or "") for f in ("summary", "why_clarify", "question"))
    if BANNED_PATTERNS.search(text):
        # 18절: "AI가 생성해서 생긴 문제"라는 표현 금지
        return None, "금지 표현 포함"

    # 근거 없는 finding 금지. 줄 번호는 해당 함수 범위 안이어야 한다.
    spans = {side["file"]: (side["start_line"], side["end_line"])
             for side in (pair["a"], pair["b"])}
    evidence = []
    for item in data.get("evidence") or []:
        file = item.get("file")
        if file not in spans:
            continue
        lo, hi = spans[file]
        line = item.get("line") or 0
        # 범위를 벗어나거나 0이면 함수 시작 줄로 맞춘다. 근거가 항상 실제 코드를 가리키게 한다.
        evidence.append({"file": file, "line": line if lo <= line <= hi else lo})

    if not evidence:
        return None, "evidence 없음"

    confidence = data.get("confidence")
    try:
        confidence = round(float(confidence), 2)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "keep": True,
        "category": data.get("category") or "similar_logic_difference",
        "summary": data["summary"].strip(),
        "why_clarify": data["why_clarify"].strip(),
        "question": data["question"].strip(),
        "evidence": evidence,
        "confidence": confidence,
        "pair": {"a": f"{pair['a']['file']}:{pair['a']['name']}",
                 "b": f"{pair['b']['file']}:{pair['b']['name']}",
                 "similarity": pair.get("similarity")},
    }, None


def make_client():
    """.env 의 GEMINI_API_KEY 로 클라이언트를 만든다. 키 값은 절대 출력하지 않는다."""
    from google import genai

    load_dotenv(ENV_PATH)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise CollectError(f"GEMINI_API_KEY 가 {ENV_PATH} 에 없습니다.")
    return genai.Client(api_key=key)


def ask(client, model: str, prompt: str) -> tuple[str | None, str | None]:
    """18절 API 실패 대응 — timeout, retry 1~2회, 실패해도 전체 분석은 계속."""
    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )
    last_err = None

    for attempt in range(RETRIES + 1):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            if resp.text:
                return resp.text, None
            last_err = "빈 응답"
        except Exception as exc:                     # noqa: BLE001 — 원인을 그대로 보여준다
            last_err = f"{type(exc).__name__}: {exc}"

        if "NOT_FOUND" in last_err or "INVALID_ARGUMENT" in last_err:
            break
        if attempt < RETRIES:
            wait = QUOTA_BACKOFF if "RESOURCE_EXHAUSTED" in last_err else 8 * (attempt + 1)
            print(f"       재시도 {attempt + 1}/{RETRIES}, {wait}초 대기")
            time.sleep(wait)

    return None, last_err


def judge(clone_path: Path, pairs: list[dict], model: str = DEFAULT_MODEL,
          min_confidence: float = MIN_CONFIDENCE) -> tuple[list[dict], dict]:
    """후보 쌍을 판정해 finding 목록과 집계를 돌려준다."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 프롬프트가 바뀌면 이전 응답은 더 이상 유효하지 않다. 해시를 키에 넣어 자동 무효화한다.
    prompt_id = hashlib.sha1(PROMPT.encode("utf-8")).hexdigest()[:8]
    cache_path = CACHE_DIR / f"{clone_path.name}_{model}_{prompt_id}.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    client = make_client()
    findings, seen_questions = [], set()
    stats = {"keep": 0, "skip": 0, "dropped": 0, "error": 0, "low_confidence": 0, "duplicate": 0}
    called = 0

    for i, pair in enumerate(pairs, 1):
        key = f"{pair['a']['file']}:{pair['a']['name']}|{pair['b']['file']}:{pair['b']['name']}"

        if key in cache:
            text = cache[key]
        else:
            # quota 를 아끼려 간격을 둔다. PHASE 1에서 간격 없이 던져 하루치를 태운 적이 있다.
            if called:
                time.sleep(SPACING_SEC)
            text, err = ask(client, model, build_prompt(clone_path, pair))
            called += 1
            if err:
                stats["error"] += 1
                print(f"  [{i:3d}] ERROR    {err[:70]}")
                continue
            cache[key] = text
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                  encoding="utf-8")

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            stats["error"] += 1
            print(f"  [{i:3d}] BAD_JSON")
            continue

        finding, reason = validate(data, pair)
        if finding is None:
            stats["skip" if reason == "skip" else "dropped"] += 1
            continue

        if finding["confidence"] < min_confidence:
            stats["low_confidence"] += 1
            continue

        # 18절: 동일한 질문 중복 제거
        q = re.sub(r"\s+", " ", finding["question"]).strip().lower()
        if q in seen_questions:
            stats["duplicate"] += 1
            continue
        seen_questions.add(q)

        stats["keep"] += 1
        findings.append(finding)
        print(f"  [{i:3d}] KEEP  {finding['confidence']:.2f}  {finding['summary'][:60]}")

    findings.sort(key=lambda f: -f["confidence"])
    return findings, stats


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print("사용법: py -m judge.llm <clone경로> <pairs.json> "
              "[--model=이름] [--limit=N] [--json=파일]", file=sys.stderr)
        return 2

    clone_path, pairs_path = Path(args[0]), Path(args[1])
    model = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--model=")),
                 DEFAULT_MODEL)
    limit = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--limit=")), 0))

    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    if limit:
        pairs = pairs[:limit]

    print(f"후보 {len(pairs)}쌍 / 모델 {model} / 요청 간격 {SPACING_SEC}초\n")
    try:
        findings, stats = judge(clone_path, pairs, model)
    except CollectError as exc:
        print(f"판정 실패: {exc}", file=sys.stderr)
        return 1

    print(f"\nfinding {stats['keep']}건 / SKIP {stats['skip']} / "
          f"규칙위반 폐기 {stats['dropped']} / 낮은 confidence {stats['low_confidence']} / "
          f"중복질문 {stats['duplicate']} / 오류 {stats['error']}")

    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--json=")), None)
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
