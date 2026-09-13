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

### PHASE 1 사전 검증 — 1차 사이클 완주 (9/14). **판정 보류**
- 샘플 25개 생성 (psf/requests 함수 182개에서 선별): 유사 10 + 일관성 10 + negative 5
- `gemini-3.6-flash`, temperature 0으로 **22개 수신** (17·19·20번 미수신, 할당량 소진). 결과 **KEEP 1 / SKIP 21**
- 리콜 측정용 결정적 테스트 3건 추가 실행 (사람이 코드로 확인한 진짜 차이만 골라 구성)
- 파일 (모두 저장소 밖 `Downloads\`): `ReCode_검증샘플25.txt`, `ReCode_검증결과25.txt`,
  `ReCode_결정적테스트.txt`, `ReCode_결정적테스트_독스트링제거.txt`

## 사전 검증 결과 — 1차 사이클

### 정밀도(오탐 안 내는가): 통과
- negative 5개 **전부 SKIP**
- 28건 전체에서 **의도를 단정한 문장 0건**. KEEP 응답도 "~인가요?" 확인 질문으로 끝남. 규칙 1·2번이 프롬프트로 통제됨
- → **13.5절 "중단" 기준은 확실히 벗어남** (중단 조건은 "거의 모든 후보를 의미 있다고 판단하거나 의도를 계속 지어냄")

### 리콜(진짜를 잡아내는가): 측정은 됐으나 저장소가 부적합

결정적 테스트 3쌍 (모두 사람이 코드로 확인한 실제 차이):

| 쌍 | 독스트링 있음 | 독스트링 제거 |
|---|---|---|
| `api.py: get ↔ head` (`allow_redirects` 기본값) | SKIP | SKIP |
| `sessions.py: get ↔ head` (동일 패턴, `sessions.py:692`) | SKIP | SKIP |
| `cookies.py: _find ↔ _find_no_duplicates` (중복 시 `CookieConflictError`) | SKIP | **KEEP** |
| **합계** | **0/3** | **1/3** |

**메커니즘은 작동한다.** 독스트링을 제거하자 `_find` 쌍이 KEEP으로 뒤집혔고, 그 응답은 목표 품질을 만족:
- `why_clarify`가 코드에서 검증 가능한 사실만 기술
- `question`이 "…첫 번째 쿠키 값을 반환하는 것이 의도된 동작인가요?" — 단정이 아닌 확인 질문
- confidence 0.9

**SKIP의 원인은 모델이 아니라 검증 저장소다.** SKIP 사유가 일관되게 세 가지:
1. "독스트링에 명시된 의도적인 동작" — requests는 의도적 차이를 전부 문서화해둠
2. "**requests 라이브러리의** 의도된 설계" — 모델이 이 유명 라이브러리를 이미 학습해 알고 있음(코드를 읽는 게 아니라 기억을 꺼냄)
3. "HTTP 프로토콜 사양 / 표준적인 동작" — 표준을 따르므로 물어볼 것이 없음

Re:Code의 타깃은 정반대(문서 없고 유명하지 않고 내부 규칙이 설명 안 된 저장소)이므로,
13.2절이 추천한 `psf/requests`는 **이 도구를 검증하기에 부적합한 corpus**였다.

### 불안정성 신호 (13.5절 "축소" 해당)
11번(`api.post`↔`Session.post`)과 12번(`api.put`↔`Session.put`)은 **같은 상황인데 SKIP/KEEP으로 갈림**.
temperature 0인데도 갈림. 대소문자 차이는 `models.py:471`·`sessions.py:542`의 `.upper()` 정규화 때문에
실제로는 무의미하므로 12번이 오탐. AI Studio 웹에서 손으로 돌린 1건도 같은 오탐을 냈음.

## In Progress

- PHASE 1 **판정 보류**. 정밀도는 통과, 리콜은 corpus 문제로 측정 불가.
  → 다른 저장소로 2차 사이클을 돌려야 GO/축소가 갈림.

## Next

1. **2차 검증 저장소 선정** — 조건: Python, 유명하지 않을 것(모델이 학습하지 않았을 것),
   독스트링이 얇을 것, 유사 로직이 실제로 반복될 것. 13.2절의 `psf/cachecontrol`은 여전히 유명 계열이라 재검토 필요
2. **2차 사이클 실행** — 스크립트는 `scripts/` 에 커밋되어 있음. 저장소 URL만 정하면 약 10분

   ```powershell
   py -m analyzer.collect https://github.com/<owner>/<repo>
   py -m scripts.make_samples repos/<owner>__<repo> cache/검증샘플25.txt
   py -m scripts.run_validation cache/검증샘플25.txt cache/검증결과25.txt
   # true_positive_test.py 의 CASES 를 그 저장소에 맞게 손으로 채운 뒤
   py -m scripts.true_positive_test repos/<owner>__<repo> cache/결정적테스트.txt
   py -m scripts.true_positive_test repos/<owner>__<repo> cache/결정적테스트_독스트링제거.txt --strip-docstrings
   ```

   - `scripts/check_models.py` — 429/404가 났을 때 남아 있는 모델 확인
   - `run_validation.py` 는 성공한 응답을 `cache/검증응답캐시.json` 에 쌓는다. 할당량이 떨어지면 같은 명령을 다시 실행하면 실패분만 이어서 받는다
   - **`true_positive_test.py` 의 `CASES` 는 사람이 직접 채워야 한다.** 저장소마다 "진짜 차이"가 다르므로 자동 생성할 수 없다. 현재 값은 psf/requests 기준
3. **GO / 축소 판정** (13.5절)
4. GO면 `judge/` 잠금 해제 후 PHASE 3(`judge/extract.py`) 착수
5. 축소면 ①②는 "후보 제시 + 질문 생성" 수준으로 유지하고 **③④⑥ + 인수인계 문서화**를 핵심 제품으로

> 어느 쪽으로 결론나든 `analyzer/`(③④⑥)는 살아남는다. 13.5절 축소·중단 양쪽 모두 ③④⑥을 핵심으로 둔다.
> PHASE 2·4는 이미 완료되어 있으므로 판정이 늦어져도 개발이 막히지 않는다.

## 설계에 반영해야 할 발견

- **함수 두 개만 잘라 던지면 안 된다.** 13.3절이 "가능하면 주변 코드 일부"를 요구하는데 1차 샘플에 이를 빼먹었다.
  그 결과 `.upper()` 정규화를 볼 수 없어 오탐이 났다. PHASE 5·6에서 후보를 만들 때 **호출 경로/정규화 지점을 함께 제공**해야 한다
- **코드 유사도 ≠ 의미 유사도.** `difflib` 0.82인 쌍이 실제로는 완전히 무관한 경우가 다수였다
  (`models.py:ok` ↔ `utils.py:is_ipv4_address` 등). PHASE 5 임베딩 후보 축소에서 같은 함정이 재현될 수 있다
- **독스트링이 있으면 모델이 "문서화된 의도"로 보고 SKIP한다.** 제품 관점에서는 올바른 동작이지만,
  데모 저장소를 고를 때 이 특성을 고려해야 한다 (PHASE 16 데모 저장소 조건)

## Known Problems

- **팀 공용 키의 Gemini 무료 할당량 소진 (9/14).** 소진된 모델: `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`. 원인은 초기 실행에서 요청 간격 없이 25건을 연속 호출한 것. 현재 스크립트는 7초 간격 + 429시 65초 백오프 적용됨.
  - **할당량은 키(프로젝트) 단위이고, 같은 키 안에서도 모델별로 따로 걸린다.**
  - 사용자 개인 키를 새로 발급해 `.env`의 `GEMINI_API_KEY`를 교체하여 해소함. 팀원 로컬 `.env`는 그대로이므로 팀원은 리셋까지 위 모델들을 못 씀
- **`gemini-2.5-flash`는 신규 사용자에게 막힘.** 404와 함께 `gemini-3.6-flash` 사용 권고 메시지 반환. `judge/llm.py`는 3.6-flash 이상을 기준으로 작성할 것
- **참고 문서 2개가 저장소에 없음.** `ReCode_개발환경_및_세부실행계획.md`, `ReCode_개발계획서.md`. `CLAUDE.md`가 참조하는데 로컬에도 git에도 없음. 현재 사용 중인 사본(`Downloads\`)은 **Gemini 전환 전 판본** — 1.3절이 아직 "Claude API / OpenAI embedding", 290줄이 "console.anthropic.com", 3절 트리에 `analyzer/ # A 담당` 주석이 남아 2절 "폴더 분업을 두지 않는다"와 모순. 갱신 후 커밋 필요
- `ReCode_개발계획서.md` 7.2절 500자 심사 폼 답변, 4절 아키텍처 설명에 "Claude API" 표현 잔존. 갱신 필요
- 1차 사이클의 검증 샘플·결과 원본이 저장소 밖(`Downloads\ReCode_*.txt`)에 있어 릴레이로 전달되지 않음. `cache/` 는 gitignore 대상이라 재실행해도 커밋되지 않음. 판정 근거 원본을 팀이 공유해야 한다면 별도 위치를 정해야 함 (결론과 수치는 본 STATUS.md에 기록됨)
- `scripts/` 는 3절 프로젝트 구조에 없는 디렉터리다. 제품 코드(`analyzer/` · `judge/`)가 아니라 PHASE 1 검증 도구라 분리했음

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
