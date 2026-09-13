# Current Status

**Updated: 2026-09-14 (일) 새벽**

## Done

### 환경 세팅 (PHASE 0) — 9/12
- Python 3.12 설치 및 `py -3.12 -m venv .venv` 활성화
- `pip install -r requirements.txt` 완료 후 `pip freeze`로 락 커밋 · push
- Docker Desktop `postgres:16` 컨테이너 healthy 확인, `psql`로 접속 검증
- `uvicorn app.main:app --reload` → `http://localhost:8000` 에서 `{"status":"ok"}` 응답 확인
- GitHub PAT 발급, `.env` 로컬 작성 (`GITHUB_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`)
- `git config --global core.autocrlf true`
- GitHub 저장소 `team-recode/recode` 생성, 초기 커밋 및 락 커밋 push
- 팀원 Collaborator 초대 및 `.env` 공유 완료

### 의존성 교체 — 9/14 (커밋 `e5bee20`)
- `anthropic`, `openai` 제거 → `google-genai`, `sentence-transformers` 설치
- `pip freeze > requirements.txt` 재커밋 (41줄 추가, 3줄 삭제)
- `torch`, `transformers`, `scikit-learn`, `scipy` 등 부수 패키지 38개 포함
- `websockets` 17.1 → 16.1.1 다운그레이드 (`google-genai`가 상한을 검). 현재 사용처 없어 무해
- 9/12 락 커밋의 Known Problem 1번 해소

### PHASE 2 — Repository 수집 (9/14)
- `analyzer/collect.py` 구현. 14절 스펙대로
- 완료 조건 통과: `py -m analyzer.collect https://github.com/psf/requests`
  → `repos/psf__requests` 생성, `commit_count` 6494, `head_sha` 확인
- `subprocess`로 `git clone` (GitPython 안 씀), 재클론 안 함, 실패 사유 노출, 최대 300초 제한
- **GitHub API는 쓰지 않음.** 14절이 요구하는 6개 필드가 전부 git 명령으로 나오고, private repo 미지원이라 토큰 불필요
- 얕은 clone(`--depth`) 안 씀 — `commit_count`와 PHASE 4 High-Churn이 전체 이력을 요구

### PHASE 4 — 정적 Evidence (9/14)
- `analyzer/static_check.py` — 16.1 High-Churn Hotspot + 16.2 Dead-Code Candidate
- `analyzer/test_map.py` — 16.3 Test Evidence Gap
- psf/requests 기준 검증 결과:
  - High-Churn(60일) **0건** — 버그 아님. 최근 60일 커밋 10개가 전부 CI 설정/pre-commit 범프라 `.py` 변경이 0. 365일로 넓혀 `git log` 집계와 12/9/9/9/7/7/7/6 정확히 일치 확인
  - Dead-Code **89건** (confidence 내림차순)
  - Test Evidence: production 22개 중 13개 연결, 9개 근거 없음. `utils.py→test_utils.py`, `adapters.py→test_adapters.py` 등 정상 연결
- 16.2 / 16.3이 지정한 표현을 `message` 필드로 데이터에 박아둠. 표현 규칙이 PHASE 7까지 유실되지 않게 한 조치이며, report 계층 몫이라고 보면 제거 가능

### PHASE 1 사전 검증 — 부분 실행 (9/14, **미완**)
- 샘플 25개 생성 (psf/requests 함수 182개에서 선별): 유사 10 + 일관성 10 + negative 5
- `gemini-3.6-flash`, temperature 0으로 **22개 수신** (17·19·20번은 할당량 소진으로 미수신)
- 결과: **KEEP 1 / SKIP 21**
- 파일: `Downloads\ReCode_검증샘플25.txt`, `Downloads\ReCode_검증결과25.txt` (저장소 밖)

## 사전 검증에서 지금까지 확인된 것

**"중단" 기준은 벗어남.** 13.5절 중단 조건은 "거의 모든 후보를 의미 있다고 판단하거나 의도를 계속 지어냄"인데 정반대.
- negative 5개 **전부 SKIP** — 오탐 없음
- **의도를 단정한 문장 관측되지 않음**. KEEP 1건조차 "정규화되어 동일하게 처리되는지 확인이 필요합니다"로 끝남. 규칙 1번이 프롬프트로 통제됨

**"GO"라고 할 근거는 아직 없음.** 단, 모델 능력 문제라고 단정할 수 없음:
- 샘플 25개에 **정답이 SKIP인 문제만 들어 있었음**. 리콜(진짜를 잡아내는지)을 잴 문제를 주지 않았음
- 11번(`api.post`↔`Session.post`)과 12번(`api.put`↔`Session.put`)은 **같은 상황인데 SKIP/KEEP으로 갈림**. temperature 0인데도 불안정 → 13.5절 "축소" 신호
- AI Studio 웹에서 손으로 돌린 1건은 대소문자 차이를 KEEP으로 판정했으나, `models.py:471`과 `sessions.py:542`의 `.upper()` 정규화 때문에 **실제로는 무의미한 차이**였음 (오탐)

**미완 항목 — 이것부터 해야 판정 가능:**
`true_positive_test.py`로 **실제 차이가 있는 쌍 3개**를 돌려 리콜을 재야 함. 사람이 코드로 확인한 진짜 차이:
1. `api.py: get ↔ head` — `get`은 `allow_redirects` 미지정(기본 True), `head`는 `setdefault(False)` (`api.py:113`)
2. `sessions.py: get ↔ head` — 동일 패턴 (`sessions.py:692`)
3. `cookies.py: _find ↔ _find_no_duplicates` — 후자는 중복 시 `CookieConflictError`, 전자는 첫 일치 반환

## In Progress

- PHASE 1 사전 검증 미완. **Gemini 무료 할당량 소진으로 중단됨.**

## Next

1. **새 API 키 발급** — 할당량은 키(프로젝트) 단위. 개인 계정으로 새 키를 만들면 즉시 재개 가능. 아니면 리셋 대기
2. **결정적 테스트 3건 실행** → GO / 축소 판정
3. GO면 `judge/` 잠금 해제 후 PHASE 3(`judge/extract.py`) 착수
4. 축소면 13.5절대로 ①②는 "후보 제시 + 질문 생성" 수준으로만 유지하고 **③④⑥ + 인수인계 문서화**가 핵심 제품

> 어느 쪽으로 결론나든 `analyzer/`(③④⑥)는 살아남는다. 13.5절 축소·중단 양쪽 모두 ③④⑥을 핵심으로 둔다.

## Known Problems

- **Gemini 무료 할당량 소진 (9/14).** 소진된 모델: `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`. 팀 공용 키라 팀원도 영향받음. 원인은 초기 실행에서 요청 간격 없이 25건을 연속 호출한 것. 현재 스크립트는 7초 간격 + 429시 65초 백오프 적용됨
- **`gemini-2.5-flash`는 신규 사용자에게 막힘.** 404와 함께 `gemini-3.6-flash` 사용 권고 메시지 반환. `judge/llm.py`는 3.6-flash 이상을 기준으로 작성할 것
- **참고 문서 2개가 저장소에 없음.** `ReCode_개발환경_및_세부실행계획.md`, `ReCode_개발계획서.md`. `CLAUDE.md`가 참조하는데 로컬에도 git에도 없음. 현재 사용 중인 사본(`Downloads\`)은 **Gemini 전환 전 판본** — 1.3절이 아직 "Claude API / OpenAI embedding", 290줄이 "console.anthropic.com", 3절 트리에 `analyzer/ # A 담당` 주석이 남아 2절 "폴더 분업을 두지 않는다"와 모순. 갱신 후 커밋 필요
- `ReCode_개발계획서.md` 7.2절 500자 심사 폼 답변, 4절 아키텍처 설명에 "Claude API" 표현 잔존. 갱신 필요
- 검증 샘플·결과 파일이 저장소 밖(`Downloads\`)에 있어 릴레이로 전달되지 않음. 저장소에 넣을지 결정 필요

## 다음 사람이 알아야 할 도구 특성

- **vulture는 후보를 찾으면 exit 3을 낸다** (1이 아님). `ExitCode(NoDeadCode=0, InvalidInput=1, InvalidCmdlineArguments=2, DeadCode=3)`. exit 1은 문법 오류 파일만 건너뛰고 나머지 스캔은 계속되므로 실패로 처리하면 안 됨
- **Windows 콘솔 인코딩**: Python이 stdout을 cp949로 씀. JSON을 파일로 리다이렉트하면 한글이 cp949로 저장됨. PowerShell 화면 출력은 정상
- `python-dotenv`의 `load_dotenv()`는 **스크립트 파일 위치**에서 위로 올라가며 `.env`를 찾는다. 저장소 밖 스크립트에서는 경로를 명시해야 함
- `analyzer/test_map.py`는 `static_check.py`의 `EXCLUDE_DIRS`·`iter_python_files`를 import한다. 3절 구조가 공용 util 파일을 허용하지 않아 모듈 간 import로 처리함
- `high_churn()`의 출력 키는 16.1이 정한 `commits_60d` 고정. `days` 인자를 바꿔 부르면 키 이름과 실제 창이 어긋남

## 참고 규약

- 세션 시작 전 `git pull`, 종료 전 `git push`
- 새 패키지 설치 시 즉시 `pip freeze > requirements.txt` 커밋
- 세부 규약은 `CLAUDE.md` / `AGENTS.md`
