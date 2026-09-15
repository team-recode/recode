"""PHASE 1 사전 검증 — 샘플을 Gemini에 돌려 JSON 답변을 받는다.

판정(USEFUL / AMBIGUOUS / NOT_USEFUL)은 사람이 한다(13.4절).
이 스크립트는 답변을 받아 모아둘 뿐 자동 채점하지 않는다.

성공한 응답은 캐시에 쌓이므로, 할당량이 떨어지면 같은 명령을 다시 실행해
실패한 것만 이어서 받을 수 있다.

사용법:
    py -m scripts.run_validation cache/검증샘플25.txt cache/검증결과25.txt
    py -m scripts.run_validation <샘플> <결과> gemini-3.6-flash --only=11,12,13
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
CACHE_PATH = REPO_ROOT / "cache" / "검증응답캐시.json"

# gemini-3.6-flash 는 9/14 목록에서 사라짐(신규 사용자 접근 제거 추정).
# 2차 사이클(mhctools)에서 CASES 6/6 을 실제로 통과시킨 모델로 갱신.
# quota 소진 시 CLI 3번째 인자로 다른 모델(gemini-flash-latest 등) 지정.
DEFAULT_MODEL = "gemini-3-flash-preview"
RETRIES = 2            # 18절 API 실패 대응: 1~2회 재시도
SPACING_SEC = 7        # 무료 티어 분당 요청 제한(대략 10 RPM) 대비 간격
QUOTA_BACKOFF = 65     # 429는 분 단위 창이 리셋될 때까지 기다린다

BLOCK_RE = re.compile(r"^\[(\d{2})\] (.+?)\s+\(참고:.*?\)$", re.MULTILINE)


def parse_blocks(path: Path) -> list[dict]:
    """샘플 파일을 블록으로 쪼갠다. '참고:' 헤더는 사람용이라 LLM에 주지 않는다."""
    text = path.read_text(encoding="utf-8")
    marks = list(BLOCK_RE.finditer(text))
    blocks = []

    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end]
        body = "\n".join(l for l in body.splitlines() if not l.startswith("====")).strip()
        blocks.append({"no": int(m.group(1)), "kind": m.group(2).strip(), "prompt": body})

    return blocks


def make_client() -> genai.Client:
    """.env 의 GEMINI_API_KEY 로 클라이언트를 만든다. 키 값은 절대 출력하지 않는다."""
    load_dotenv(ENV_PATH)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(f"GEMINI_API_KEY 가 {ENV_PATH} 에 없습니다.")
    return genai.Client(api_key=key)


def ask(client, model: str, prompt: str) -> tuple[str | None, str | None]:
    """(응답텍스트, 오류) 를 돌려준다. 실패해도 전체 분석은 계속된다(18절)."""
    config = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
    )
    last_err = None

    for attempt in range(RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            if resp.text:
                return resp.text, None
            last_err = "빈 응답"
        except Exception as exc:                     # noqa: BLE001 — 원인을 그대로 보여준다
            last_err = f"{type(exc).__name__}: {exc}"

        # 모델명 오류나 잘못된 요청은 다시 보내도 같은 결과다. 즉시 포기한다.
        if "NOT_FOUND" in last_err or "INVALID_ARGUMENT" in last_err:
            break

        if attempt < RETRIES:
            wait = QUOTA_BACKOFF if "RESOURCE_EXHAUSTED" in last_err else 8 * (attempt + 1)
            print(f"       재시도 {attempt + 1}/{RETRIES}, {wait}초 대기")
            time.sleep(wait)

    return None, last_err


def summarize(text: str) -> tuple[str, str]:
    """응답에서 (KEEP/SKIP, 한 줄 요약)을 뽑는다."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return "BAD_JSON", text[:120]
    keep = "KEEP" if data.get("keep") else "SKIP"
    return keep, (data.get("summary") or data.get("reason") or "")


def resolve(arg: str) -> Path:
    path = Path(arg)
    return path if path.is_absolute() else REPO_ROOT / path


def main() -> int:
    if len(sys.argv) < 3:
        print("사용법: py -m scripts.run_validation <샘플파일> <결과파일> [모델] [--only=1,2]",
              file=sys.stderr)
        return 2

    sample_path, out_path = resolve(sys.argv[1]), resolve(sys.argv[2])
    model = next((a for a in sys.argv[3:] if not a.startswith("--")), DEFAULT_MODEL)

    client = make_client()
    blocks = parse_blocks(sample_path)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    wanted = {int(x) for x in only.split(",")} if only else None
    todo = [b for b in blocks
            if str(b["no"]) not in cache and (wanted is None or b["no"] in wanted)]

    print(f"샘플 {len(blocks)}개 / 캐시됨 {len(cache)} / 이번에 받을 것 {len(todo)}")
    print(f"모델 {model} / temperature 0 / 요청 간격 {SPACING_SEC}초\n")

    for i, b in enumerate(todo):
        if i:
            time.sleep(SPACING_SEC)
        text, err = ask(client, model, b["prompt"])
        if text:
            cache[str(b["no"])] = text
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
            keep, summary = summarize(text)
        else:
            keep, summary = "ERROR", err or ""
        print(f"  [{b['no']:02d}] {b['kind'][:14]:14s} {keep:8s} {summary[:58]}")

    # 결과 파일은 캐시 전체로 매번 다시 쓴다.
    lines = [f"# PHASE 1 사전 검증 결과 — 모델 {model}, temperature 0\n",
             "# 판정(O / X / △)은 사람이 직접 적는다. 13.4절.\n"]
    stats = {"KEEP": 0, "SKIP": 0, "BAD_JSON": 0}
    neg_skip = missing = 0

    for b in blocks:
        text = cache.get(str(b["no"]))
        if not text:
            missing += 1
            body, keep = "(아직 응답 없음 — 스크립트를 다시 실행하세요)", "MISSING"
        else:
            keep, _ = summarize(text)
            stats[keep] = stats.get(keep, 0) + 1
            body = text
            if b["kind"].startswith("negative") and keep == "SKIP":
                neg_skip += 1

        lines.append(f"\n{'=' * 78}\n[{b['no']:02d}] {b['kind']}  ->  {keep}\n{'=' * 78}\n")
        lines.append(body.strip() + "\n")
        lines.append("\n사람 판정: [ O / X / △ ]   메모:\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines), encoding="utf-8")

    print(f"\nKEEP {stats['KEEP']} / SKIP {stats['SKIP']} / "
          f"JSON오류 {stats['BAD_JSON']} / 미수신 {missing}")
    print(f"negative 중 SKIP: {neg_skip}")
    print(f"결과 저장: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
