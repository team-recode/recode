"""PHASE 10 — FastAPI 연결(22절).

최소 API 3개. `analyze.py` 파이프라인을 BackgroundTasks 로 감싼다.
큐(Celery/Redis)는 두지 않는다 — 1.4절에서 FastAPI BackgroundTasks + jobs 테이블로 충분하다고 결정.

    uvicorn app.main:app --reload
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (BackgroundTasks, Depends, FastAPI, Form, HTTPException,
                     Request)
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

import analyze
from analyzer.collect import CollectError, parse_repo_url
from app import db
from judge import embed as embed_mod
from judge import llm as llm_mod
from judge import report as report_mod

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# 23절 Landing 의 예제 저장소. 클릭하면 미리 분석해 둔 결과를 바로 연다.
# 매번 새로 돌리면 후보 100쌍 x 요청 간격 7초 = 10분이 넘어 시연에 쓸 수 없다.
EXAMPLES = [
    {"slug": "mhctools", "dir": "openvax__mhctools", "lang": "Python",
     "name": "openvax/mhctools", "url": "https://github.com/openvax/mhctools",
     "note": "같은 기능을 여러 파일이 제각각 구현한 저장소입니다"},
    {"slug": "gson", "dir": "google__gson", "lang": "Java",
     "name": "google/gson", "url": "https://github.com/google/gson",
     "note": "JSON을 쓰는 자리마다 이스케이프와 null 처리가 갈립니다"},
    {"slug": "axios", "dir": "axios__axios", "lang": "JavaScript",
     "name": "axios/axios", "url": "https://github.com/axios/axios",
     "note": "헤더를 검증하는 두 곳이 서로 다른 문자셋을 씁니다"},
    {"slug": "serilog", "dir": "serilog__serilog", "lang": "C#",
     "name": "serilog/serilog", "url": "https://github.com/serilog/serilog",
     "note": "정적 Log와 인스턴스 Logger의 인자 처리가 다릅니다"},
    {"slug": "cjson", "dir": "DaveGamble__cJSON", "lang": "C",
     "name": "DaveGamble/cJSON", "url": "https://github.com/DaveGamble/cJSON",
     "note": "배열 인덱스를 다루는 두 함수가 NULL을 다르게 봅니다"},
    {"slug": "cachecontrol", "dir": "psf__cachecontrol", "lang": "Python",
     "name": "psf/cachecontrol", "url": "https://github.com/psf/cachecontrol",
     "note": "규모가 작아 결과를 훑어보기 좋습니다"},
    # psf/requests 는 뺐다. Python 예제가 셋이라 중복이고, 언어를 하나라도 더
    # 보여주는 편이 낫다. 되살리려면 dir="psf__requests" 로 이 항목을 다시 넣으면 된다.
]

# 웹에서 새 저장소를 분석할 때의 상한. 요청 간격이 7초라 이보다 크면 화면에서 너무 오래 기다린다.
WEB_MAX_PAIRS = 20

# 23절 Progress 화면 문구. db 상태값 순서와 1:1 로 맞춘다.
STEP_LABELS = [
    (db.STATUS_CLONING, "저장소를 내려받는 중"),
    (db.STATUS_EXTRACTING, "함수를 추출하는 중"),
    (db.STATUS_EMBEDDING, "비슷한 로직을 찾는 중"),
    (db.STATUS_JUDGING, "확인할 질문을 만드는 중"),
    (db.STATUS_STATIC_ANALYSIS, "자주 바뀐 영역을 찾는 중"),
    (db.STATUS_GENERATING_REPORT, "인수인계 문서를 쓰는 중"),
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Re:Code", description="낯선 저장소 인수인계 분석기",
              lifespan=lifespan)


def get_session():
    with db.SessionLocal() as session:
        yield session


class AnalyzeRequest(BaseModel):
    repo_url: str
    # 무료 티어 quota 대비 옵션. CLI 와 같은 의미다.
    skip_llm: bool = False
    limit: int = 0

    @field_validator("repo_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        # 잘못된 URL 로 job 을 만들어두고 백그라운드에서 실패시키지 않는다.
        try:
            parse_repo_url(value)
        except CollectError as exc:
            # pydantic 은 ValueError 만 422 로 바꾼다. 그대로 두면 500 이 난다.
            raise ValueError(str(exc)) from exc
        return value.strip()


def _run_job(job_id: str, repo_url: str, skip_llm: bool, limit: int) -> None:
    """BackgroundTasks 워커. 단계마다 jobs 행을 갱신한다."""
    def on_progress(status: str, percent: int) -> None:
        with db.SessionLocal() as session:
            job = session.get(db.Job, job_id)
            if job:
                job.status, job.progress = status, percent
                session.commit()

    try:
        report_path = analyze.run(
            repo_url,
            threshold=embed_mod.DEFAULT_THRESHOLD,
            model=llm_mod.DEFAULT_MODEL,
            skip_llm=skip_llm,
            limit=limit,
            on_progress=on_progress,
        )
        result, error, status = str(report_path), None, db.STATUS_COMPLETED
    except Exception as exc:                          # noqa: BLE001 — 원인을 그대로 남긴다
        result, error, status = None, f"{type(exc).__name__}: {exc}", db.STATUS_FAILED
        print(f"[job {job_id}] 실패: {error}", file=sys.stderr)

    with db.SessionLocal() as session:
        job = session.get(db.Job, job_id)
        if job:
            job.status = status
            job.progress = 100 if status == db.STATUS_COMPLETED else job.progress
            job.result_path, job.error = result, error
            session.commit()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------- 화면 (23절)

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html", {"examples": EXAMPLES})


@app.post("/analyze")
def submit(request: Request, tasks: BackgroundTasks, repo_url: str = Form(...),
           skip_llm: str = Form(default=""), session: Session = Depends(get_session)):
    try:
        parse_repo_url(repo_url)
    except CollectError as exc:
        # 폼 제출은 422 JSON 대신 랜딩 화면에 메시지를 돌려준다.
        return templates.TemplateResponse(
            request, "landing.html",
            {"examples": EXAMPLES, "error": str(exc).splitlines()[0]}, status_code=400)

    job_id = _create_job(session, tasks, repo_url.strip(), bool(skip_llm), WEB_MAX_PAIRS)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.get("/examples/{slug}")
def open_example(slug: str, tasks: BackgroundTasks, session: Session = Depends(get_session)):
    """미리 분석해 둔 예제 결과를 바로 연다.

    시연에서 10분씩 기다릴 수 없으므로 저장된 HANDOFF.md 를 그대로 쓴다.
    결과물이 없으면(다른 PC 에서 clone 만 받은 경우 등) 평소대로 분석을 돌린다.
    """
    example = next((e for e in EXAMPLES if e["slug"] == slug), None)
    if example is None:
        raise HTTPException(status_code=404, detail="예제를 찾을 수 없습니다.")

    # 같은 결과를 가리키는 완료된 job 이 이미 있으면 그대로 재사용한다.
    done = (session.query(db.Job)
            .filter(db.Job.repo_url == example["url"], db.Job.status == db.STATUS_COMPLETED)
            .order_by(db.Job.created_at.desc()).first())
    if done and Path(done.result_path or "").is_file():
        return RedirectResponse(f"/jobs/{done.id}/report", status_code=303)

    report = analyze.OUTPUT_ROOT / example["dir"] / "HANDOFF.md"
    if not report.is_file():
        job_id = _create_job(session, tasks, example["url"], False, WEB_MAX_PAIRS)
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    job = db.Job(id=db.new_job_id(), repo_url=example["url"],
                 status=db.STATUS_COMPLETED, progress=100, result_path=str(report))
    session.add(job)
    session.commit()
    return RedirectResponse(f"/jobs/{job.id}/report", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def progress_page(request: Request, job_id: str, session: Session = Depends(get_session)):
    job = _load(job_id, session)
    if job.status == db.STATUS_COMPLETED:
        return RedirectResponse(f"/jobs/{job_id}/report", status_code=303)

    return templates.TemplateResponse(request, "progress.html", {
        "job": job.as_status(),
        "steps": STEP_LABELS,
        "order": [key for key, _ in STEP_LABELS],
    })


@app.get("/jobs/{job_id}/report", response_class=HTMLResponse)
def report_page(request: Request, job_id: str, session: Session = Depends(get_session)):
    job = _load(job_id, session)
    if job.status != db.STATUS_COMPLETED:
        return RedirectResponse(f"/jobs/{job_id}", status_code=303)

    path = Path(job.result_path or "")
    if not path.is_file():
        raise HTTPException(status_code=410, detail="보고서 파일이 없습니다. 다시 분석하세요.")

    # 화면과 마크다운이 같은 근거를 쓰도록 gather_evidence 를 공유한다.
    clone_path = Path("repos") / path.parent.name
    findings_path = path.parent / "findings.json"
    findings = (json.loads(findings_path.read_text(encoding="utf-8"))
                if findings_path.is_file() else [])
    data = report_mod.gather_evidence(clone_path, findings)

    # 할당량으로 중간에 끊긴 분석이면 화면 맨 위에도 알린다. 남은 시간은 볼 때마다 다시 센다.
    metrics_path = path.parent / "metrics.json"
    metrics = (json.loads(metrics_path.read_text(encoding="utf-8"))
               if metrics_path.is_file() else {})
    quota = llm_mod.quota_notice(metrics.get("quota_stopped", False),
                                 metrics.get("skipped_by_quota", 0),
                                 metrics.get("models_used"))

    return templates.TemplateResponse(request, "report.html", {
        "d": data,
        "job_id": job_id,
        "quota": quota,
        # 외부 모델이 실제로 본 코드량. 분석할 때 재서 metrics.json 에 넣어둔 값이다.
        "privacy": metrics.get("privacy"),
        "markdown": path.read_text(encoding="utf-8"),
        # 상단에 이미 나온 파일은 아래 표에서 뺀다(19절 근거 중복 금지).
        "touched": [row["file"] for row in data["before_you_touch"]],
    })


@app.get("/jobs/{job_id}/download")
def download(job_id: str, session: Session = Depends(get_session)):
    job = _load(job_id, session)
    path = Path(job.result_path or "")
    if job.status != db.STATUS_COMPLETED or not path.is_file():
        raise HTTPException(status_code=409, detail="아직 내려받을 보고서가 없습니다.")
    return FileResponse(path, media_type="text/markdown", filename="HANDOFF.md")


def _create_job(session: Session, tasks: BackgroundTasks, repo_url: str,
                skip_llm: bool, limit: int) -> str:
    """API 와 폼 제출이 같은 경로로 job 을 만든다."""
    job = db.Job(id=db.new_job_id(), repo_url=repo_url,
                 status=db.STATUS_QUEUED, progress=0)
    session.add(job)
    session.commit()
    tasks.add_task(_run_job, job.id, repo_url, skip_llm, limit)
    return job.id


@app.post("/api/analyze")
def create_analysis(req: AnalyzeRequest, tasks: BackgroundTasks,
                    session: Session = Depends(get_session)) -> dict:
    return {"job_id": _create_job(session, tasks, req.repo_url, req.skip_llm, req.limit)}


@app.get("/api/jobs/{job_id}/stream")
async def stream(job_id: str):
    """23절 Progress 화면용 SSE. 상태가 바뀔 때만 이벤트를 보낸다."""

    async def events():
        last = None
        while True:
            with db.SessionLocal() as session:
                job = session.get(db.Job, job_id)
                if job is None:
                    yield {"event": "done",
                           "data": json.dumps({"status": "failed",
                                               "error": "job_id 를 찾을 수 없습니다."})}
                    return
                snapshot = (job.status, job.progress, job.error)

            status, progress, error = snapshot
            if snapshot != last:
                last = snapshot
                yield {"event": "progress",
                       "data": json.dumps({"status": status, "progress": progress})}

            if status in (db.STATUS_COMPLETED, db.STATUS_FAILED):
                yield {"event": "done",
                       "data": json.dumps({"status": status, "error": error})}
                return

            await asyncio.sleep(1)

    return EventSourceResponse(events())


def _load(job_id: str, session: Session) -> db.Job:
    job = session.get(db.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_id 를 찾을 수 없습니다.")
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)) -> dict:
    return _load(job_id, session).as_status()


@app.get("/api/jobs/{job_id}/report", response_class=PlainTextResponse)
def get_report(job_id: str, session: Session = Depends(get_session)) -> str:
    job = _load(job_id, session)

    if job.status == db.STATUS_FAILED:
        raise HTTPException(status_code=409, detail=job.error or "분석에 실패했습니다.")
    if job.status != db.STATUS_COMPLETED:
        # 아직 도는 중이면 진행 상황을 알려준다. 빈 보고서를 주지 않는다.
        raise HTTPException(status_code=409,
                            detail=f"아직 분석 중입니다. status={job.status}, "
                                   f"progress={job.progress}")

    path = Path(job.result_path or "")
    if not path.is_file():
        raise HTTPException(status_code=410, detail="보고서 파일이 없습니다. 다시 분석하세요.")
    return path.read_text(encoding="utf-8")
