"""PHASE 10 — 분석 job 테이블(22절).

22절이 "복잡하게 만들지 않는다" 고 못 박았으므로 테이블 하나만 둔다.
큐도 두지 않는다. FastAPI BackgroundTasks + 이 테이블로 충분하다(1.4절 Celery/Redis 제외 결정).
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 22절 "분석 job 상태". 순서는 실제 파이프라인 진행 순서다.
STATUS_QUEUED = "queued"
STATUS_CLONING = "cloning"
STATUS_EXTRACTING = "extracting"
STATUS_EMBEDDING = "embedding"
STATUS_JUDGING = "judging"
STATUS_STATIC_ANALYSIS = "static_analysis"
STATUS_GENERATING_REPORT = "generating_report"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

RUNNING_STATUSES = (
    STATUS_QUEUED, STATUS_CLONING, STATUS_EXTRACTING, STATUS_EMBEDDING,
    STATUS_JUDGING, STATUS_STATIC_ANALYSIS, STATUS_GENERATING_REPORT,
)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    repo_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default=STATUS_QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # 보고서 본문이 아니라 경로만 둔다. HANDOFF.md 는 outputs/ 에 이미 저장된다.
    result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 브라우저마다 쿠키로 발급하는 익명 UUID. 로그인이 아니라
    # "같은 브라우저가 동시에 두 개 돌리지 않도록" 을 위한 식별자다.
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def as_status(self) -> dict:
        """GET /api/jobs/{id} 응답."""
        body = {"job_id": self.id, "status": self.status, "progress": self.progress,
                "repo_url": self.repo_url,
                "created_at": self.created_at.isoformat() if self.created_at else None}
        if self.error:
            body["error"] = self.error
        return body


engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine else None


def init_db() -> None:
    """앱 시작 시 테이블을 만든다. 마이그레이션 도구는 8일 일정에 과하다."""
    if engine is None:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _fail_orphaned_jobs()


def _add_missing_columns() -> None:
    """create_all 은 새 컬럼을 기존 테이블에 넣어주지 않는다.

    Alembic 을 들이기엔 이르고, 한 컬럼짜리 상황이라 손으로 검사한다.
    """
    inspector = inspect(engine)
    if not inspector.has_table("jobs"):
        return
    existing = {col["name"] for col in inspector.get_columns("jobs")}
    if "session_id" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN session_id VARCHAR(32)"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_session_id ON jobs (session_id)"))


def _fail_orphaned_jobs() -> None:
    """서버가 내려가면 BackgroundTasks 는 함께 사라진다.

    그때 진행 중이던 job 행은 `judging` 같은 상태로 영원히 남아
    사용자에게는 끝나지 않는 진행 화면이 된다. 기동 시 정리한다.
    """
    with SessionLocal() as session:
        orphans = session.query(Job).filter(Job.status.in_(RUNNING_STATUSES)).all()
        for job in orphans:
            job.status = STATUS_FAILED
            job.error = "서버가 재시작되어 분석이 중단되었습니다. 다시 시도하세요."
        if orphans:
            session.commit()
            print(f"중단된 job {len(orphans)}건을 failed 로 정리했습니다.")


def new_job_id() -> str:
    return uuid.uuid4().hex
