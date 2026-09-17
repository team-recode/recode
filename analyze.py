"""PHASE 8 — Re:Code CLI 진입점(20절).

웹 없이 한 명령으로 제품 핵심이 동작한다.

    py analyze.py https://github.com/psf/requests

과정: clone -> extract -> static evidence -> embedding -> LLM -> report -> HANDOFF.md

LLM 단계는 무료 티어 quota 에 걸릴 수 있다. `--skip-llm` 을 주면 ①② 없이
정적 근거(③④⑥)만으로 보고서를 만든다. 13.5절 축소 시나리오와 같은 출력이다.
"""

import json
import sys
import time
from pathlib import Path

from analyzer.collect import CollectError, collect
from judge import embed as embed_mod
from judge import llm as llm_mod
from judge import report as report_mod

OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs"


def _step(n: int, total: int, label: str) -> float:
    print(f"[{n}/{total}] {label}")
    return time.time()


def _done(started: float, detail: str = "") -> None:
    print(f"      {detail} ({time.time() - started:.1f}초)" if detail
          else f"      ({time.time() - started:.1f}초)")


def run(url: str, threshold: float, model: str, skip_llm: bool,
        limit: int = 0, on_progress=None) -> Path:
    """분석 파이프라인 전체. `on_progress(status, percent)` 로 진행 상황을 흘려보낸다.

    status 문자열은 22절이 정한 job 상태명을 그대로 쓴다. FastAPI 워커가 그대로 DB에 넣는다.
    """
    total = 4 if skip_llm else 5
    wall = time.time()

    def notify(status: str, percent: int) -> None:
        if on_progress:
            on_progress(status, percent)

    notify("cloning", 5)
    started = _step(1, total, f"저장소 수집: {url}")
    meta = collect(url)
    clone_path = Path(meta["clone_path"])
    clone_sec = round(time.time() - started, 1)
    _done(started, f"{meta['owner']}/{meta['repo']} 커밋 {meta['commit_count']}개, "
                   f"head {meta['head_sha'][:7]}")

    out_dir = OUTPUT_ROOT / clone_path.name
    out_dir.mkdir(parents=True, exist_ok=True)

    # extract 는 embed 내부에서 호출된다. 함수 추출과 임베딩을 따로 돌리지 않는다.
    notify("extracting", 15)
    started = _step(2, total, f"함수 추출 및 유사 후보 축소 (threshold {threshold})")
    pairs, kept, _ = embed_mod.build(clone_path, threshold=threshold)
    embed_sec = round(time.time() - started, 1)
    notify("embedding", 35)
    (out_dir / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    _done(started, f"함수 {len(kept)}개 -> 후보 {len(pairs)}쌍")

    findings, stats, judged, llm_sec = [], {}, 0, 0.0
    if skip_llm:
        # 건너뛴 단계에는 번호를 주지 않는다. 남은 단계 번호가 어긋나면 진행 상황이 헷갈린다.
        print("      LLM 판정 건너뜀 (--skip-llm). 정적 근거만으로 보고서를 만든다")
    else:
        targets = pairs[:limit] if limit else pairs
        judged = len(targets)
        note = f", 전체 {len(pairs)}쌍 중 --limit" if limit and limit < len(pairs) else ""
        notify("judging", 40)
        started = _step(3, total, f"LLM 판정 ({model}, 후보 {judged}쌍{note})")
        findings, stats = llm_mod.judge(clone_path, targets, model=model)
        llm_sec = round(time.time() - started, 1)
        (out_dir / "findings.json").write_text(
            json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
        detail = (f"finding {stats['keep']}건 / SKIP {stats['skip']} / "
                  f"폐기 {stats['dropped']} / 오류 {stats['error']} "
                  f"/ API {stats['api_calls']}회 · 캐시 {stats['cache_hits']}회")
        used = stats.get("models_used") or []
        if len(used) > 1:
            # 도중에 모델이 바뀌었다면 어떤 순서로 썼는지 남긴다. 결과 해석에 필요하다.
            detail += f" / 모델 {' -> '.join(used)}"
        if stats.get("quota_stopped"):
            detail += f" / 할당량 소진으로 {stats['skipped_by_quota']}쌍 건너뜀"
        _done(started, detail)

    notify("static_analysis", 88)
    step = total - 1
    started = _step(step, total, "정적 근거 수집 (High-Churn / Dead-Code / Test Gap)")
    # 할당량으로 중간에 끊겼으면 보고서 맨 위에 그 사실을 적는다.
    # 적지 않으면 finding 이 적은 것이 "확인할 게 없는 저장소"로 읽힌다.
    quota = llm_mod.quota_notice(stats.get("quota_stopped", False),
                                 stats.get("skipped_by_quota", 0),
                                 stats.get("models_used"))
    # 저장소의 어느 정도가 외부 모델로 나갔는지. 말이 아니라 줄 수로 보여준다.
    privacy = None if skip_llm else llm_mod.sent_code_summary(clone_path, pairs, judged)
    text = report_mod.build(clone_path, findings, quota, privacy)
    static_sec = round(time.time() - started, 1)
    _done(started)

    notify("generating_report", 95)
    started = _step(total, total, "HANDOFF.md 생성")
    report_path = out_dir / "HANDOFF.md"
    report_path.write_text(text, encoding="utf-8")
    _done(started, f"{len(text.splitlines())}줄 / 섹션 {text.count(chr(10) + '## ')}개")

    _write_metrics(out_dir, {
        "repo": f"{meta['owner']}/{meta['repo']}",
        "url": url,
        "head_sha": meta["head_sha"],
        "commit_count": meta["commit_count"],
        "model": None if skip_llm else model,
        # 시작 모델이 할당량으로 막히면 다른 모델로 갈아탄다. 실제로 쓴 목록을 따로 남긴다.
        "models_used": stats.get("models_used", []),
        "threshold": threshold,
        # 21절 측정 항목 ------------------------------------------------
        "clone_time_sec": clone_sec,
        "analysis_time_sec": round(time.time() - wall, 1),
        "embed_time_sec": embed_sec,
        "llm_time_sec": llm_sec,
        "static_time_sec": static_sec,
        "functions_total": len(kept) + 0,          # 필터 통과 함수 수
        "candidate_pairs": len(pairs),
        "judged_pairs": judged,
        # 임베딩은 sentence-transformers 로컬 실행이라 외부 호출이 0이다.
        "embedding_api_calls": 0,
        "llm_api_calls": stats.get("api_calls", 0),
        "llm_cache_hits": stats.get("cache_hits", 0),
        "llm_tokens": stats.get("tokens", 0),
        # 무료 티어를 쓰므로 실제 과금은 없다. 토큰 수를 근거로 함께 남긴다.
        "estimated_cost_usd": 0.0,
        "findings": stats.get("keep", 0),
        "skipped": stats.get("skip", 0),
        "dropped_by_rules": stats.get("dropped", 0),
        "errors": stats.get("error", 0),
        # 할당량 때문에 중간에 끊겼는지. 판정 수가 적은 이유를 나중에 설명할 수 있어야 한다.
        "quota_stopped": stats.get("quota_stopped", False),
        "skipped_by_quota": stats.get("skipped_by_quota", 0),
        # 외부 모델이 실제로 본 코드량. 화면과 보고서가 같은 값을 쓴다.
        "privacy": privacy,
        # useful / ambiguous / not_useful 은 사람이 라벨링한다(21절). 여기서 채우지 않는다.
        "human_labels": None,
    })

    return report_path


def _write_metrics(out_dir: Path, metrics: dict) -> None:
    """21절 측정 기록. 사람 평가 항목은 비워두고 라벨링 결과로 따로 채운다."""
    metrics["measured_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      측정 기록: {(out_dir / 'metrics.json').name}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print("사용법: py analyze.py https://github.com/owner/repo\n"
              "  --threshold=0.80   유사도 하한\n"
              "  --model=이름       첫 LLM 모델 (소진되면 다음 모델로 자동 교체)\n"
              "  --limit=N          후보 N개만 판정 (quota 절약)\n"
              "  --skip-llm         LLM 없이 정적 근거만으로 보고서 생성",
              file=sys.stderr)
        return 2

    threshold = float(next((a.split("=", 1)[1] for a in sys.argv
                            if a.startswith("--threshold=")), embed_mod.DEFAULT_THRESHOLD))
    model = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--model=")),
                 llm_mod.DEFAULT_MODEL)
    limit = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--limit=")), 0))

    try:
        report_path = run(args[0], threshold, model, "--skip-llm" in sys.argv, limit)
    except CollectError as exc:
        print(f"\n분석 실패: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n중단됨.", file=sys.stderr)
        return 130

    print("\nAnalysis complete.")
    print(f"Report: {report_path.relative_to(Path(__file__).resolve().parent).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
