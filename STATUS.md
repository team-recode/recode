# Current Status

**Updated: 2026-09-12 (금) 저녁**

## Done

### 환경 세팅 (PHASE 0)
- Python 3.12 설치 및 `py -3.12 -m venv .venv` 활성화
- `pip install -r requirements.txt` 완료 후 `pip freeze`로 락 커밋 · push
- Docker Desktop `postgres:16` 컨테이너 healthy 확인, `psql`로 접속 검증
- `uvicorn app.main:app --reload` → `http://localhost:8000` 에서 `{"status":"ok"}` 응답 확인
- GitHub PAT 발급, `.env` 로컬 작성 (`GITHUB_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`)
- `git config --global core.autocrlf true`
- GitHub 저장소 `team-recode/recode` 생성, 초기 커밋 및 락 커밋 push
- 팀원 Collaborator 초대 및 `.env` 공유 완료

### 결정
- **AI 스택 전환**: Claude API + OpenAI embedding 원안 → Google Gemini 무료 티어 + sentence-transformers 로컬로 확정 (유료 API 사용 안 함)
- 순차 릴레이 개발 방식 확정 (폴더 소유권 없음)

### 문서 정리
- `ReCode_개발환경.md` 삭제 (팀원이 상위집합으로 병합)
- `ReCode_개발환경_및_세부실행계획.md`에 Gemini 반영, `git add .` 규약 완화, 트리 주석 정리
- `CLAUDE.md` · `AGENTS.md` 초안 커밋 (본 커밋 예정)
- `STATUS.md` 도입 (본 파일)

## In Progress

- 없음. 오늘은 여기까지 마감.

## Next

1. **9/13 오전 첫 순서**: ①② 사전 검증
   - Google AI Studio에서 함수 쌍 25개 판정 (유사 10 + 일관성 10 + negative 5)
   - `ReCode_개발환경_및_세부실행계획.md` 13절의 GO/축소/중단 기준으로 방향 결정
   - `judge/` 코드는 이 결정 전까지 시작하지 않는다
2. **①② 검증 통과 시**: 저장소 `requirements.txt` 교체 (`anthropic`, `openai` → `google-genai`, `sentence-transformers`), 락 재커밋
3. **PHASE 2 착수**: `analyzer/collect.py` (검증 결과와 무관하게 병렬 진행 가능)

## Known Problems

- 저장소 락 커밋(9/12)에는 아직 `anthropic`, `openai`가 남아 있음. `judge/` 코딩 시작 전 반드시 교체 필요.
- `ReCode_개발계획서.md` 7.2절 500자 심사 폼 답변, 4절 아키텍처 설명에 "Claude API" 표현이 잔존. ①② 검증 결과 확정 후 Gemini로 갱신 필요.
- Anthropic Console / OpenAI 계정은 만들지 않음 (Gemini만 발급). 문제 아님, 참고용.

## 참고 규약

- 세션 시작 전 `git pull`, 종료 전 `git push`
- 새 패키지 설치 시 즉시 `pip freeze > requirements.txt` 커밋
- 세부 규약은 `CLAUDE.md` / `AGENTS.md`
