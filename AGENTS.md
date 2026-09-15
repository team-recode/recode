# 프로젝트: Re:Code

Re:Code는 낯선 저장소를 넘겨받은 개발자가, 코드를 수정하기 전에 반드시 확인해야 할 맥락 공백과 질문을 찾아주는 AI 인수인계 도구다. 코드 품질 검사기가 아니고, README/요약 생성기도 아니다.

## 릴레이 규약

- 세션 시작 전에 사용자가 `git pull`을 이미 실행했다고 가정한다. 확인이 필요하면 물어본다.
- 작업이 끝나면 커밋 · 푸시까지 완료한다. 애매하면 커밋만 하고 사용자 확인을 받는다.
- 새 패키지를 깔면 즉시 `pip freeze > requirements.txt`를 실행하고 같은 커밋에 포함한다.
- 커밋 메시지는 한국어 한 줄. 무엇을 왜 바꿨는지 다음 릴레이 주자가 이해할 수 있게.
- 계획에 없는 파일 생성 · 리팩토링 · 추상화는 하지 않는다.
- 큰 변경(구조 개편, 새 의존성, 새 모듈) 전에는 사용자에게 확인받는다.

## Re:Code 개발 원칙

- **Findings must be evidence-backed.** 근거가 없는 finding은 만들지 않는다.
- **Never infer original developer intent as fact.** 원저자의 의도를 사실로 단정하지 않는다.
- **Prefer clarification questions over definitive blame.** 잘못됐다고 단정하기보다 확인 질문을 만든다.
- Do not add features outside the current PHASE (참고: `ReCode_개발환경_및_세부실행계획.md` 11~29절).
- Do not perform broad refactors unless explicitly asked.
- Before adding a dependency, explain why it is needed.
- After installing a dependency, update `requirements.txt`.
- Never read, print, or commit secrets from `.env`.
- Never commit `repos/`.
- Keep changes small and easy for the next developer/agent to understand.

## 커밋 전 확인

`git add .`은 금지하지 않는다. 다만 실행 전에 `git status`로 스테이징 대상을 훑고, `.env`·대용량 캐시·모델 파일이 실수로 잡히지 않는지 확인한다.

## 현재 단계 (2026-09-16 갱신)

**PHASE 0~9 완료.** CLI 완성(`analyze.py`), 4개 저장소 finding 31건 측정, PHASE 15/16 준비 자료 정리.

**진입 phase**:
- **PHASE 10 (오늘)**: FastAPI 백엔드. 22절 스펙. `POST /api/analyze`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/report`. `analyze.py` 를 워커로 래핑. `jobs` 테이블 1개 (id, repo_url, status, progress, result_path, error, created_at). 8개 상태 (`queued` → `cloning` → `extracting` → `static_analysis` → `embedding` → `judging` → `generating_report` → `completed`/`failed`)
- **PHASE 11 (오늘 밤~9/17)**: 프론트 3화면 (Landing/Progress/Report). 23절. Tailwind CDN + Jinja2 + SSE (sse-starlette). Markdown copy/download. 빌드 없음

**금기 (범위 제외 확정, 5.1 일정표 개정)**:
- 배지·리더보드 만들지 않음
- 로그인·회원가입 없음
- private 저장소 미지원
- Tailwind 커스텀 빌드 없음 (CDN 만)

**다음 phase 순서** (원 계획 그대로):
- 12 자기참조 데모 (9/17): Re:Code 를 Re:Code 로 분석
- 13 사용자 테스트 3~5명 (9/17~18): **사용자 오프라인 몫**. 개발자 지인 섭외 · 라벨링 요청
- 14 배포 (9/17, Railway or Render 결정)
- 15 심사 폼 답변 갱신 (9/18 **접수 마감**). 500자 본안은 9/15 완성, PHASE 13 결과만 반영
- 16 데모 영상 촬영 (9/18~19). mhctools primary, cachecontrol backup
- 17 최종 제출물 정리 (9/19): README, 대표 이미지, 스크린샷 5장
- 9/20 **제출 마감**: 버그 수정만 (30절)

**환경 준비 상태**:
- ✅ `google-genai`, `sentence-transformers` 설치 (락 커밋 `e5bee20`, 9/14)
- ✅ `anthropic`, `openai` 제거 (사용자 PC 실측 확인)
- ⏳ **팀원 PC venv 드리프트**: `pip install -r requirements.txt` 후 `pip uninstall anthropic openai -y` 필요 (팀원 PC 만 해당, 사용자 PC 는 이미 정리됨). ⚠ 팀원 PC 에서 `pip freeze > requirements.txt` 는 **금지** (sentence-transformers 스택 소실)

**세부 사항은 `STATUS.md` 최상단 참조.**

## 참고 문서

- `ReCode_개발환경_및_세부실행계획.md` — 세팅 규약(1~8절), PHASE 0~17 세부 실행(9~36절)
- `ReCode_개발계획서.md` — 프로젝트 정의, 아키텍처, 심사 폼 답변 초안
- `STATUS.md` — 오늘까지의 진행 상황과 다음 첫 순서

## 최종 핵심 문장

방향이 흔들리면 아래로 돌아온다.

> **Re:Code는 코드를 설명하는 도구가 아니라, 다음 개발자가 무엇을 물어봐야 하는지 찾아주는 도구다.**
>
> **Every finding needs evidence. If there is no evidence, do not generate it.**
