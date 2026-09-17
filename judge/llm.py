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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from analyzer.collect import CollectError

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
CACHE_DIR = REPO_ROOT / "cache" / "llm"

# quota 는 모델별로 독립이라, 앞 모델이 하루 한도를 다 쓰면 뒤 모델로 갈아탄다.
# 순서는 판정 품질 순이다. gemini-3.6-flash 가 PHASE 1 2차 사이클에서 CASES 6/6 을 통과했다.
DEFAULT_MODEL = "gemini-3-flash-preview"
FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

RETRIES = 2            # 18절 API 실패 대응: 1~2회 재시도
SPACING_SEC = 7        # 무료 티어 분당 요청 제한 대비 간격
TIMEOUT_MS = 120_000   # 18절 timeout

# 429 는 분 단위가 아니라 하루 단위 제한(GenerateRequestsPerDayPerProjectPerModel)이다.
# 오래 기다려도 그 날 안에는 풀리지 않으므로 길게 버티지 않는다.
# 응답이 알려주는 retryDelay 가 20초라 한 번만 그만큼 쉬고 넘어간다.
QUOTA_BACKOFF = 20
QUOTA_RETRIES = 1

# 할당량 오류가 이만큼 연달아 나면 이 모델은 오늘 끝났다고 보고 다음 모델로 넘어간다.
# 1 이 아니라 2 인 이유: 429 에는 하루 한도 말고 분당 한도도 섞여 있다. 분당 한도는
# 잠깐 쉬면 풀리는데, 한 번에 모델을 갈아타면 멀쩡한 모델을 버리게 된다.
# 체인의 모든 모델이 소진되면 남은 후보를 포기하고 여기까지의 결과로 보고서를 만든다.
QUOTA_GIVE_UP = 2

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
    # 언어를 알려주지 않으면 모델이 문법을 오해한다. C# 의 `=>` 를 화살표 함수로 읽는 식이다.
    # 쌍은 항상 같은 언어끼리만 만들어지므로(judge/embed.similar_pairs) 하나면 된다.
    fence = pair.get("lang", "python")
    return (
        f"{PROMPT}\n"
        f"--- 함수 A ---\n파일: {a['file']}\n함수명: {a['name']}\n"
        f"```{fence}\n{numbered_source(clone_path, a)}\n```\n\n"
        f"--- 함수 B ---\n파일: {b['file']}\n함수명: {b['name']}\n"
        f"```{fence}\n{numbered_source(clone_path, b)}\n```\n"
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


def ask(client, model: str, prompt: str) -> tuple[str | None, str | None, int]:
    """18절 API 실패 대응 — timeout, retry 1~2회, 실패해도 전체 분석은 계속.

    (응답, 오류, 사용 토큰 수) 를 돌려준다. 토큰 수는 21절의 비용 측정에 쓴다.
    """
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
                usage = getattr(resp, "usage_metadata", None)
                return resp.text, None, getattr(usage, "total_token_count", 0) or 0
            last_err = "빈 응답"
        except Exception as exc:                     # noqa: BLE001 — 원인을 그대로 보여준다
            last_err = f"{type(exc).__name__}: {exc}"

        if "NOT_FOUND" in last_err or "INVALID_ARGUMENT" in last_err:
            break

        quota = "RESOURCE_EXHAUSTED" in last_err
        limit = QUOTA_RETRIES if quota else RETRIES
        if attempt < limit:
            wait = QUOTA_BACKOFF if quota else 8 * (attempt + 1)
            print(f"       재시도 {attempt + 1}/{limit}, {wait}초 대기")
            time.sleep(wait)
        else:
            break

    return None, last_err, 0


# 429 본문이 알려주는 무료 등급 하루 한도. 모델 하나당 이 수를 넘기면 그날은 끝이다.
#   quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: 20
FREE_TIER_RPD = 20


def _pacific_utc_offset(utc: datetime) -> int:
    """태평양 시간의 UTC 오프셋(시간). 서머타임이면 -7, 아니면 -8.

    zoneinfo 는 Windows 에서 tzdata 패키지를 따로 요구한다. 이 한 가지를 위해
    의존성을 늘리지 않으려고 직접 계산한다. 미국 서머타임 규칙은 고정되어 있다:
    3월 둘째 일요일 02:00 시작, 11월 첫째 일요일 02:00 종료.
    """
    def nth_sunday(month: int, nth: int) -> datetime:
        first = datetime(utc.year, month, 1)
        first += timedelta(days=(6 - first.weekday()) % 7)   # 그 달의 첫 일요일
        return first + timedelta(weeks=nth - 1)

    begin = nth_sunday(3, 2) + timedelta(hours=10)    # 02:00 PST = 10:00 UTC
    end = nth_sunday(11, 1) + timedelta(hours=9)      # 02:00 PDT = 09:00 UTC
    return -7 if begin <= utc < end else -8


def quota_reset_at(now: datetime | None = None) -> datetime:
    """하루 한도가 다시 열리는 시각을 이 PC 의 지역 시간으로 돌려준다.

    무료 등급의 requests-per-day 는 태평양 시간 자정에 초기화된다.
    https://ai.google.dev/gemini-api/docs/rate-limits
    429 본문의 retryDelay(18초)는 짧은 재시도 힌트일 뿐 하루 한도와는 무관하다.
    """
    now = now or datetime.now(timezone.utc)
    utc = now.astimezone(timezone.utc).replace(tzinfo=None)

    offset = _pacific_utc_offset(utc)
    pacific = utc + timedelta(hours=offset)
    midnight = datetime(pacific.year, pacific.month, pacific.day) + timedelta(days=1)
    # 자정 시점의 오프셋으로 다시 환산한다. 서머타임이 바뀌는 날 한 시간 어긋나는 것을 막는다.
    reset_utc = midnight - timedelta(hours=_pacific_utc_offset(midnight - timedelta(hours=offset)))
    return reset_utc.replace(tzinfo=timezone.utc).astimezone()


def quota_notice(stopped: bool, skipped: int = 0, models: list[str] | None = None,
                 now: datetime | None = None) -> dict | None:
    """할당량 때문에 판정을 못 끝냈을 때 보고서와 화면이 함께 쓸 안내 값.

    두 곳에서 따로 문구를 만들면 어긋난다. 여기 한 곳에서만 만든다.
    남은 시간은 부를 때마다 다시 센다. 보고서를 나중에 다시 열어도 맞는 값이 나온다.
    """
    if not stopped:
        return None

    reset = quota_reset_at(now)
    remaining = reset - (now or datetime.now(timezone.utc)).astimezone()
    return {
        "skipped": skipped,
        "models": models or [],
        "limit": FREE_TIER_RPD,
        "reset_at": reset.strftime("%m월 %d일 %H:%M"),
        # 30분 이상 남으면 올림한다. "0시간 뒤" 같은 문구가 나오지 않게 한다.
        "hours": max(1, round(remaining.total_seconds() / 3600)),
    }


def model_chain(start: str) -> list[str]:
    """시작 모델부터 순서대로 시도할 모델 목록. 중복은 없앤다."""
    chain = [start]
    chain += [m for m in FALLBACK_MODELS if m != start]
    return chain


def _cache_path(clone_path: Path, model: str, prompt_id: str) -> Path:
    return CACHE_DIR / f"{clone_path.name}_{model}_{prompt_id}.json"


def load_cache(clone_path: Path, prompt_id: str) -> dict:
    """같은 저장소·같은 프롬프트로 받은 응답은 모델이 달라도 재사용한다.

    모델을 갈아타면 캐시 파일이 갈라진다. 그때 앞 모델의 응답을 못 읽으면
    이미 판정한 쌍을 새 모델로 다시 물어보게 되고, 아끼려던 할당량을 오히려 더 쓴다.
    읽을 때는 모델별 파일을 전부 합치고, 쓸 때만 현재 모델 파일에 넣는다.
    """
    merged: dict = {}
    for path in sorted(CACHE_DIR.glob(f"{clone_path.name}_*_{prompt_id}.json")):
        try:
            merged.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue    # 깨진 캐시 하나 때문에 분석 전체를 멈추지 않는다
    return merged


def save_cache(clone_path: Path, model: str, prompt_id: str, key: str, text: str) -> None:
    """한 건 받을 때마다 바로 쓴다. 중간에 끊겨도 여기까지는 남는다."""
    path = _cache_path(clone_path, model, prompt_id)
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    entries[key] = text
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")


def judge(clone_path: Path, pairs: list[dict], model: str = DEFAULT_MODEL,
          min_confidence: float = MIN_CONFIDENCE) -> tuple[list[dict], dict]:
    """후보 쌍을 판정해 finding 목록과 집계를 돌려준다.

    한 모델의 하루 한도가 끝나면 다음 모델로 갈아탄다(`FALLBACK_MODELS`).
    체인의 모든 모델이 소진되면 남은 후보를 건너뛰고, 그때까지 얻은 finding 만 돌려준다.
    분석이 통째로 실패하는 것보다 일부라도 보고서가 나오는 편이 낫다.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 프롬프트가 바뀌면 이전 응답은 더 이상 유효하지 않다. 해시를 키에 넣어 자동 무효화한다.
    prompt_id = hashlib.sha1(PROMPT.encode("utf-8")).hexdigest()[:8]
    cache = load_cache(clone_path, prompt_id)

    client = make_client()
    chain = model_chain(model)
    mi = 0                      # 지금 쓰는 모델의 체인 위치
    findings, seen_questions = [], set()
    # 21절 측정용: 실제 API 호출과 캐시 히트를 구분해 센다. 토큰 수는 비용 근거가 된다.
    stats = {"keep": 0, "skip": 0, "dropped": 0, "error": 0, "low_confidence": 0,
             "duplicate": 0, "api_calls": 0, "cache_hits": 0, "tokens": 0,
             "skipped_by_quota": 0, "quota_stopped": False, "models_used": []}
    quota_streak = 0

    for i, pair in enumerate(pairs, 1):
        key = f"{pair['a']['file']}:{pair['a']['name']}|{pair['b']['file']}:{pair['b']['name']}"

        if key in cache:
            text = cache[key]
            stats["cache_hits"] += 1
        elif stats["quota_stopped"]:
            # 체인의 모든 모델이 소진됐다. 남은 후보는 호출하지 않고 넘긴다.
            stats["skipped_by_quota"] += 1
            continue
        else:
            # 모델을 갈아타면 같은 쌍을 새 모델로 한 번 더 시도한다. 그래서 while 이다.
            while True:
                # quota 를 아끼려 간격을 둔다. PHASE 1에서 간격 없이 던져 하루치를 태운 적이 있다.
                if stats["api_calls"]:
                    time.sleep(SPACING_SEC)
                current = chain[mi]
                if current not in stats["models_used"]:
                    stats["models_used"].append(current)
                text, err, tokens = ask(client, current, build_prompt(clone_path, pair))
                stats["api_calls"] += 1
                stats["tokens"] += tokens

                if not err or "RESOURCE_EXHAUSTED" not in err:
                    quota_streak = 0
                    break

                quota_streak += 1
                if quota_streak < QUOTA_GIVE_UP:
                    break       # 분당 한도일 수 있다. 이 쌍은 넘기고 다음 쌍에서 다시 본다
                if mi + 1 >= len(chain):
                    # 쓸 수 있는 모델을 다 썼다. 여기까지의 결과로 보고서를 만든다.
                    stats["quota_stopped"] = True
                    print(f"  [{i:3d}] 모델 {len(chain)}개 모두 할당량 소진. "
                          f"남은 후보를 건너뛰고 여기까지의 결과로 보고서를 만듭니다.")
                    break
                mi, quota_streak = mi + 1, 0
                print(f"  [{i:3d}] {current} 할당량 소진 -> {chain[mi]} 로 전환합니다.")

            if err:
                stats["error"] += 1
                if not stats["quota_stopped"]:
                    print(f"  [{i:3d}] ERROR    {err[:70]}")
                continue
            cache[key] = text
            save_cache(clone_path, chain[mi], prompt_id, key, text)

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

    chain = model_chain(model)
    print(f"후보 {len(pairs)}쌍 / 요청 간격 {SPACING_SEC}초")
    print("모델 순서: " + " -> ".join(chain))
    print()
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
