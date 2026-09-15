# Current Status

**Updated: 2026-09-15 (월) — PHASE 3·5·6·7 완료, 파이프라인 연결됨**

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

### PHASE 1 사전 검증 — 2차 사이클 착수, 도중 중단 (9/14 오후)

**저장소 선정: `openvax/mhctools`** ★102 · 73 py파일 · Apache-2.0
- 도메인 특화(MHC binding predictor Python wrapper, 바이오인포). 모델 학습 확률 낮음
- 여러 predictor를 같은 인터페이스로 감싸는 구조 → wrapper 반복 패턴이 명확
- 후보 3개(mhctools / crugroup/spade ★55 / lobbyboy-ssh/lobbyboy ★242) 중 규모·낯섦·구조 모두 만족

**진행 완료**
- `py -m analyzer.collect https://github.com/openvax/mhctools` → `repos/openvax__mhctools` (611커밋, head `c8ca5ba`)
- `py -m scripts.make_samples repos/openvax__mhctools cache/mhctools_샘플25.txt` → **함수 466개 → 상한 250개 → 쌍 22개** (유사 7 / 일관성 10 / negative 5). psf/requests(22개)와 동일 규모
- `py -m scripts.run_validation cache/mhctools_샘플25.txt cache/mhctools_결과22.txt` → **4/22 수신 후 quota 소진**. 캐시 `cache/검증응답캐시.json`에 [1,2,3,5] 남아 있음

**부분 데이터에서 이미 나온 시그널 (강)**
- **Sample [02] = KEEP.** `base_commandline_predictor.py:predict` ↔ `base_predictor.py:predict_with_flanks` 쌍. 응답 요약: "predict_with_flanks 는 flanks 를 받아 그대로 전달하지만, base 메서드는 무시함"
- 이 KEEP 응답이 **아래 CASES 후보 1과 동일한 패턴**을 잡아냄. 유명 라이브러리가 아닌 저장소에서도 도구가 실제 override 차이를 찾아냈다는 증거
- 응답 품질 심층 확인(프롬프트 규칙 1~5 대조): `why_clarify` 는 코드 사실만("검증 결과에서 플랭크 반환값 2·3번째 항목을 버리고"), `question` 은 확인 질문("의도된 동작인가요?"), confidence 0.85, evidence 배열 존재. **규칙 4개 통과, 유일한 약점은 `evidence[].line=0`** (프롬프트 예시값을 그대로 반환 — 프롬프트 개선 여지 있으나 판정에는 영향 없음)
- **캐시 SKIP 3건 사유 분석 (강한 시그널)**: 
  - [1] `_find_deepimmuno_home` ↔ `_find_deeptap_home`: "동일 구조의 함수, 도구별 이름 차이 외 논리적 불일치 없음"
  - [3] `parses` ↔ `_normalize_output_allele`: "역할과 목적이 서로 다름"
  - [5] `_mhcflurry_presentation_status` ↔ `_mhcflurry_affinity_status`: "인자 값 차이는 모델 종류별 설정 차이에서 기인, 모순/오류 없음"
  - **SKIP 사유가 전부 코드 구조 분석 기반**. psf/requests 1차 사이클의 코퍼스 편향 사유(`"라이브러리의 의도된 설계"`, `"표준적 동작"`) 같은 도피성 답변 **0건**. 모델이 **기억을 꺼내는 게 아니라 코드를 읽는 중** → mhctools 가 검증 corpus 로 적합하다는 강한 GO 방향 시그널

**CASES(리콜 테스트용) 3쌍 확정 — mhctools 기준**

| 번호 | A | B | 사람이 확인한 진짜 차이 |
|---|---|---|---|
| T1 | `base_predictor.py:predict_with_flanks` | `mhcflurry.py:predict_with_flanks` | base 는 flanks 를 검증만 하고 버린 채 `predict(peptide_list)` 호출. mhcflurry override 는 flanks 를 predict 에 그대로 넘김 |
| T2 | `calis.py:_check_peptides` | `eramer.py:_check_peptides` | eramer 만 `n <= self.epitope_length` 조건이 추가로 있음 |
| T3 | `caphla.py:_check_peptides` | `deepimmuno.py:_check_peptides` | caphla 는 AA 유효성 검증 있음, deepimmuno 는 length 만 검증 |

**`scripts/true_positive_test.py` CASES 튜플 형식 확장** — mhctools 의 실제 override 패턴이 cross-file 이라 필요.
- 원 형식: `(rel, funcA, funcB, truth)` — 같은 파일 내 두 함수
- 새 형식: `(fileA, funcA, fileB, funcB, truth)` — 파일 넘나드는 두 함수도 지원. 같은 파일이면 `fileA==fileB`
- `get_func` 등 핵심 로직은 손대지 않음. `main()` 의 CASES 소비 부분과 프롬프트에 파일 경로 표기만 갱신
- Same-file 대안(3후보) 실측 결과: 2개는 sample [05]·[07]과 중복(독립 신호 아님), 1개는 이름 유사성이 낮아 리콜 테스트로 약함. cross-file 확장이 더 나은 판정 근거

**부수 확인 — `analyzer/` mhctools 스모크 테스트 (9/14 오후, quota 대기 중)**
- `py -m analyzer.static_check repos/openvax__mhctools` → **정상 실행**. 결과 캐시: `cache/mhctools_static.json`
  - **High-Churn(60일): 20건.** psf/requests 는 60일 창에서 0건이었으므로 극단적 대비. `mhctools/__init__.py` 22회로 최상위(predictor 추가마다 등록되는 파일). 나머지는 4~5회 균등 분포. mhctools 는 현재 활발히 유지되는 저장소라 실제 인수인계 시나리오에 더 가깝다는 방증
  - Dead-Code: 39건 (variable 20 / function 9 / attribute 5 / method 3 / property 2). 규모상 psf/requests(89건)보다 작음
- `py -m analyzer.test_map repos/openvax__mhctools` → **정상 실행**. 결과 캐시: `cache/mhctools_testmap.json`
  - production 73개 중 **연결 52개(71%), 근거 없음 21개(29%)**. 근거 없는 파일이 대부분 `netmhc_pan.py`·`netmhc_cons.py`·`netmhc*.py` 계열. `tests/` 에 실제 테스트가 있어도 파일명이 매칭 규칙(`test_<모듈>.py`)과 다르면 못 잡는 한계 확인. 16.3 원 정의대로 "직접 연결된 근거를 찾지 못함"이라 단정하지 않고 표기하는 방침 유지
- **결론**: `analyzer/`(③④⑥) 는 두 번째 저장소에서도 문제 없이 도는 것 확인. GO/축소 판정과 별개로 살아남는 모듈의 안정성 확보

**Quota 이력 — 부분 리셋 반복**
- `gemini-3.6-flash` 는 `check_models` 목록에서 사라짐. 신규 사용자에게 접근 제거된 것으로 보임
- `gemini-flash-latest` : 첫 리셋 후 4건 성공하고 다시 429/503 발생. 무료 티어 daily quota 가 예상보다 훨씬 낮음
- `gemini-3-flash-preview` : **다른 quota 버킷.** CASES 6건 완주 성공. **CLI 인자로 명시적 지정 필수**
- `gemini-2.5-flash-lite` : 404 NOT_FOUND (막힘)
- 결론: **모델별 quota 가 완전히 독립.** 하나 소진되면 다른 모델로 즉시 전환하는 방식이 실무. 스크립트 CLI 3번째 인자로 지원됨

## 사전 검증 결과 — 2차 사이클 (mhctools). **GO 판정**

### 정밀도 (오탐 안 내는가): 통과 (부분 데이터)

sample 8/22 수신 (KEEP 1 / SKIP 7, 미수신 14):

- **negative 5개 중 수신한 1건(pair 21) SKIP.** 나머지 4건 미수신
- **의도를 단정한 문장 0건.** 8건 전체에서 SKIP 사유가 모두 코드 구조 분석("동일 구조", "역할이 서로 다름", "각 목적에 맞는 정규화")
- psf/requests 1차의 코퍼스 편향 사유(`"라이브러리의 의도된 설계"`, `"표준적 동작"`) **재현되지 않음**. 모델이 기억이 아닌 코드를 읽음

### 리콜 (진짜 차이를 잡는가): **완전 통과** — 최대 신호

결정적 테스트 3쌍(사람이 코드로 확인한 진짜 차이) × 2조건 = 6건:

| 쌍 | 독스트링 유지 | 독스트링 제거 |
|---|---|---|
| T1 `predict_with_flanks` (base 무시 vs mhcflurry 사용) | **KEEP** | **KEEP** |
| T2 `_check_peptides` (calis vs eramer `epitope_length`) | **KEEP** | **KEEP** |
| T3 `_check_peptides` (caphla AA 검증 vs deepimmuno 없음) | **KEEP** | **KEEP** |
| **합계** | **3/3** | **3/3** |

psf/requests(0/3, 1/3)와 극명한 대조. 응답 요약도 정확:
- T1: "서브클래스 구현에서 베이스 클래스의 입력 유효성 검사 로직이 누락됨"
- T2: "펩타이드 유효성 검사 시 길이 제한 참조 방식과 추가 제약 조건의 차이"
- T3: "동일한 목적의 함수 간 아미노산 유효성 검사 로직의 일관성 부족"

### 판정: **GO (13.5절 기준 충족)**

- 정밀도(중단 조건: 거의 모든 후보 KEEP 또는 의도 단정 지속): **벗어남**
- 리콜(축소 조건: 진짜 차이를 못 잡음): **벗어남** (6/6 잡음)
- Corpus 편향 문제도 해소됨
- **`judge/` 잠금 해제.** PHASE 3(`judge/extract.py`) 착수 가능

### PHASE 3 — 함수 추출 및 절삭 (9/15)

`judge/extract.py` 구현. 15절 스펙대로. **완료 조건 3개 전부 통과:**

| 완료 조건 | 결과 |
|---|---|
| requests 수준 저장소에서 함수 목록 생성 | 711개(테스트 포함) / 268개(`--no-tests`) |
| django 같은 대형 저장소에서 2,000개 상한 작동 | py 2,616파일 → **정확히 2,000개**, 17.8초 |
| 함수 추출 때문에 메모리가 폭발하지 않음 | **피크 36MB** (`tracemalloc` 실측) |

- 출력 필드는 15절 그대로 + `is_test` 추가 (15절 "테스트 파일도 추출은 하되 임베딩 후보에서 필요에 따라 제외"를 호출측이 판단할 수 있게)
- `signature` 는 `ast.unparse` 로 생성. `async def` 여부와 반환 타입까지 담아 PHASE 5에서 유실되지 않게 함
- **상한 처리 방식**: 커밋 수 내림차순으로 파일을 정렬해 앞에서부터 추출하고, 상한에 닿으면 멈춘다.
  파일 중간에서 자르지 않으므로 한 파일의 함수가 반만 남는 일이 없다.
  django 실측 결과 남은 15개 파일이 전부 커밋 최상위(`db/models/query.py` 643회 ~ 최저 284회)
- 파싱 실패 파일은 건너뛴다. 근거로 쓸 수 없는 것은 추측하지 않는다

**`analyzer/test_map.py` 의 `_commit_counts` → `commit_counts` 로 공개 이름 변경.**
`judge/extract.py` 가 같은 계산(파일별 커밋 수)을 필요로 해 복제 대신 재사용했다.
호출부 1곳 포함 2줄 변경. `test_evidence_gap` 회귀 확인 완료(psf/requests 22개 파일 동일).

### PHASE 5 — 임베딩 기반 후보 축소 (9/15)

`judge/embed.py` 구현. 17절 스펙. 임베딩은 원안의 OpenAI 대신 **로컬 `sentence-transformers`**(`all-MiniLM-L6-v2`, 약 90MB, API 호출·과금 없음).

**threshold = 0.80 확정.** 17절 지시("고정하지 않고 저장소 2~3개를 돌려보며 정한다")대로 세 저장소 실측:

| threshold | requests(148) | mhctools(437) | django(679) |
|---|---|---|---|
| 0.70 | 93 | 1091 | 679 |
| 0.75 | 53 | 532 | 295 |
| **0.80** | 32 | 245 | 116 |
| 0.85 | 12 | 137 | 50 |
| 0.90 | 5 | 71 | 16 |

**단일 threshold 로는 세 저장소를 모두 목표 구간(수십~100)에 넣을 수 없다.** 그래서 threshold 는
품질 하한으로만 쓰고, 실제 개수 제한은 `MAX_PAIRS=100` 이 한다. 최종 결과: **requests 35 / mhctools 100 / django 100**.

- 임베딩 캐시: `cache/embeddings/{repo}_{sha12}_{model}.npz`. 같은 commit SHA면 재계산하지 않는다(17절).
  함수 목록이 캐시와 어긋나면 자동으로 다시 계산한다
- cosine 은 numpy 내적(벡터를 정규화해 저장). 전수 LLM 비교 없음

**후보 선별에서 발견한 것 — 유사도 내림차순 정렬은 이 제품에 틀린 전략이다.**

처음 구현은 PHASE 1 이 검증한 3쌍을 **하나도 후보에 넣지 못했다.** 원인 셋을 실측으로 잡아 고침:

| 결함 | 증상 | 수정 |
|---|---|---|
| 최상위 문장만 세는 길이 필터 | `eramer._check_peptides` 는 **976자인데 for 루프 하나**라 "1문장"으로 잡혀 제거됨. `MIN_BODY_STATEMENTS=2` 가 실제 후보를 통째로 날림 | 문장을 `ast.walk` 로 중첩까지 센다. 하한은 1로 낮추고 실질 차단은 `MIN_SOURCE_CHARS=80` 이 한다 |
| 완전 동일 복사본이 상위 독식 | 유사도 1.000 쌍이 최상위. ①②는 **차이**를 묻는 기능이라 물어볼 게 없음 | 정규화 후 동일하면 제외 + `MAX_SIMILARITY=0.97` 상한 |
| 한 함수가 후보를 독식 | `predict_dataframe` 한 무리가 100개를 다 채움. 후보 유사도 범위가 0.915~0.969 로 좁음 | `MAX_PER_FUNCTION=1` — `scripts/make_samples.py` 에서 이미 쓴 다양성 제한과 같은 방식 |

수정 후 **T1(`base_predictor` ↔ `mhcflurry` 의 `predict_with_flanks`)이 #39(0.906)로 복귀**,
후보 유사도 범위도 0.807~0.969 로 넓어짐.

**남은 한계(의도적 수용)**: `MAX_PER_FUNCTION=1` 때문에 PHASE 1 의 T2·T3 와 **정확히 같은 조합**은 안 나온다
(`calis` 가 더 유사한 `caphla` 와 먼저 짝지어짐). 다만 `_check_peptides` 계열이 4쌍 올라오므로
다음 개발자가 받는 질문("파일마다 `_check_peptides` 구현이 다른데 의도된 것인가")은 동일하다.
CASES 는 리콜 측정용으로 사람이 고른 것이지 embed 의 출력 명세가 아니다.

### PHASE 6 — LLM 판정 (9/15)

`judge/llm.py` 구현. 18절 스펙. 모델 `gemini-3-flash-preview`, temperature 0.

**PHASE 1 의 프롬프트 약점 해결 — `evidence[].line = 0` 문제.**
원인은 프롬프트가 줄 번호를 줄 방법이 없었던 것. 두 가지로 고침:
1. 소스를 **실제 줄 번호를 붙여서** 넘긴다(`  207 |     def predict_with_flanks(...)`)
2. 응답의 line 이 0이거나 함수 범위 밖이면 **함수 시작 줄로 보정**한다. 근거가 항상 실제 코드를 가리키게 강제
→ 실측 결과 `evidence.line = 0` **0건**, 모두 실제 줄 번호(92·112·157·461 등)

**18절 강제 규칙 구현 상태**

| 규칙 | 구현 |
|---|---|
| JSON schema 강제 | `response_mime_type="application/json"` + 응답 필드 검증. 필수 필드가 비면 폐기 |
| 근거 없는 finding 금지 | evidence 가 비었거나 두 함수 파일과 무관하면 폐기 |
| 작성자 의도 단정 금지 | 프롬프트 규칙 1·2 (PHASE 1 검증본 그대로) |
| "AI가 생성해서 생긴 문제" 표현 금지 | 프롬프트 규칙 7 + `BANNED_PATTERNS` 정규식으로 후단에서 한 번 더 차단 |
| 동일한 질문 중복 제거 | 질문 텍스트 정규화 후 중복 제거 |
| 낮은 confidence 제외 | `MIN_CONFIDENCE = 0.5` |
| API 실패 대응 | timeout 120초, retry 2회, 429는 65초 백오프, 실패 후보는 건너뛰고 계속 |

**실행 중 발견 — 품질 이탈을 규칙 9·10 으로 잡음.**
1차 실행(15쌍)에서 13건 KEEP 이 나왔는데 그중 둘이 제품 정의에서 벗어났다:
- "일관성을 위해 `__str__` 출력에 `program_name` 을 **추가할 필요가 있습니까**" → 질문이 아니라 **개선 제안**
- "`__str__` 메서드 내 **따옴표 사용 일관성** 부족" → 동작과 무관한 **스타일 지적**

Re:Code 는 코드 품질 검사기가 아니므로 프롬프트에 규칙 2개를 추가:
- 규칙 9: 코드를 고치라고 제안하지 마라. question 은 "왜 이렇게 되어 있는지" 를 묻는 형태여야 한다
- 규칙 10: 동작에 영향 없는 스타일 차이(따옴표·공백·이름 표기)만으로는 finding 을 만들지 마라

재실행(8쌍) 결과 **두 건 모두 SKIP 으로 전환**, 남은 5건은 전부 "~한 이유가 무엇인가요?" 형태.

**프롬프트 해시를 캐시 키에 넣음.** `cache/llm/{repo}_{model}_{prompt_sha8}.json`.
프롬프트가 바뀌면 이전 응답이 자동 무효화된다. 규칙 9·10 을 추가했을 때 실제로 필요했다.

**레이어링**: `judge/llm.py` 는 `make_client`·retry 상수를 자체 보유한다.
처음엔 `scripts/run_validation` 에서 import 했으나 **제품 코드가 검증 도구에 의존하는 역방향**이라 되돌렸다.
`scripts/` 쪽 프롬프트(`PROMPT_HEAD`)는 PHASE 1 재현용으로 원본을 유지하므로 `judge/llm.py` 의 것과 **의도적으로 다르다**(18절 규칙 6~10 추가분).

### PHASE 7 — HANDOFF.md 생성 (9/15)

`judge/report.py` 구현. 19절 문서 구조 7개 섹션. `analyzer/`(③④⑥) + `judge/llm.py`(①②) 를 합친다.

**19절 출력 원칙 구현 상태**

| 원칙 | 구현 |
|---|---|
| 결과 0건인 섹션은 숨긴다 | 실측 확인 — psf/requests 는 60일 churn 0건 + finding 0건이라 **섹션 1·5·6·7 만 출력**(4개), mhctools 는 7개 전부 |
| 모든 finding 에 Evidence | finding 은 PHASE 6 에서 evidence 검증을 통과한 것만 들어온다. 각 질문 아래 `파일:줄` 로 표기 |
| 경고 개수를 부풀리지 않는다 | 섹션당 최대 10행 + "그 외 N개". 아래 테스트 파일 제외 조치도 이 원칙 때문 |
| 같은 근거를 여러 섹션에서 중복 출력하지 않는다 | 섹션 2에 나온 파일은 섹션 4·5 목록에서 제외 |
| 질문은 최대 5~10개 | `MAX_QUESTIONS = 10` |
| 첫 주 할 일은 최대 3개 | `MAX_FIRST_WEEK = 3`, 19절 우선순위 순서(high-churn+test gap → consistency → dead-code) |

**PHASE 6 에서 넘긴 "의미 중복 질문" 해결.** 같은 함수 쌍에 대한 finding 을 묶어 대표 1건만 보여주고
나머지는 `"같은 패턴이 2곳에서 더 보인다"` 로 덧붙인다. mhctools 실측에서 기본 `mode` 차이 3건이 1건으로 합쳐졌다.
사실을 숨기지 않으면서 개수는 부풀리지 않는다.

**리포트 계층에서 테스트 파일을 제외.** `analyzer/` 는 16절대로 테스트를 포함해 모든 근거를 낸다(그대로 유지).
다만 인수인계 문서가 물어볼 대상은 앞으로 고칠 production 코드다. 거르기 전에는
dead-code 상위 10건 중 9건이 `tests/` 의 미사용 변수였고 "그 외 45개"로 표시됐다.
거른 뒤에는 `_predict_protein_flank_length`·`VALID_CLASS_I_METHODS` 같은 실제 확인 대상이 올라오고 "그 외 19개" 로 줄었다.

**섹션 번호는 19절 고정값을 유지한다.** 0건 섹션을 숨기면 번호가 `1 → 5 → 6 → 7` 처럼 건너뛴다.
저장소가 달라도 "## 5 는 항상 Test evidence gaps" 가 유지되도록 일부러 재번호를 매기지 않았다.
보기 문제라고 판단되면 재번호로 바꿀 수 있다.

## In Progress

- PHASE 7 완료. **①②③④⑥ 전체 파이프라인이 CLI 로 연결됨.** 다음은 **PHASE 8(CLI MVP 완성)**

## Next

**PHASE 8 — CLI MVP 완성** (계획서 20절)

현재는 단계별 CLI 를 손으로 이어 붙여야 한다. 20절대로 한 번에 도는 진입점을 만든다.

현재 전체 파이프라인 (mhctools 기준 실행 순서):
```powershell
py -m analyzer.collect https://github.com/openvax/mhctools
py -m judge.embed repos/openvax__mhctools --threshold=0.80 --json=cache/mhctools_pairs.json
py -m judge.llm repos/openvax__mhctools cache/mhctools_pairs.json --json=cache/mhctools_findings.json
py -m judge.report repos/openvax__mhctools cache/mhctools_findings.json --out=HANDOFF.md
```

- 20절의 "이 단계 완료 전 금지" 항목을 먼저 확인할 것
- `judge/embed.py` 가 내부에서 `judge/extract.py` 를 부르므로 extract 는 따로 실행할 필요 없음

**부수 작업**:
- 남은 sample 14건은 quota 회복되는 대로 재실행 (판정에는 필수 아님, 정밀도 재확인용). CLI 인자로 `gemini-3-flash-preview` 지정
- ✅ `DEFAULT_MODEL` 갱신 완료 (9/14 저녁): `gemini-3.6-flash` → `gemini-3-flash-preview`. mhctools 리콜 6/6 통과 모델로 확정
- ⏳ **Venv 드리프트 정리는 다음 세션으로 연기.** CLAUDE.md 지침대로 `pip uninstall anthropic openai -y` 필요하나, PHASE 3 착수 세션 시작 시 함께 처리. `sentence-transformers` 스택은 PHASE 5 시작 시 설치. 지금 `requirements.txt` 재생성은 부작용(sentence-transformers 항목 소실) 있어 보류

> `analyzer/`(③④⑥) + `judge/`(①②) 가 이제 함께 살아있는 상태. PHASE 3~7 순서대로 진행.


## 설계에 반영해야 할 발견

- **함수 두 개만 잘라 던지면 안 된다.** 13.3절이 "가능하면 주변 코드 일부"를 요구하는데 1차 샘플에 이를 빼먹었다.
  그 결과 `.upper()` 정규화를 볼 수 없어 오탐이 났다. PHASE 5·6에서 후보를 만들 때 **호출 경로/정규화 지점을 함께 제공**해야 한다
- **코드 유사도 ≠ 의미 유사도.** `difflib` 0.82인 쌍이 실제로는 완전히 무관한 경우가 다수였다
  (`models.py:ok` ↔ `utils.py:is_ipv4_address` 등). PHASE 5 임베딩 후보 축소에서 같은 함정이 재현될 수 있다
- **독스트링이 있으면 모델이 "문서화된 의도"로 보고 SKIP한다.** 제품 관점에서는 올바른 동작이지만,
  데모 저장소를 고를 때 이 특성을 고려해야 한다 (PHASE 16 데모 저장소 조건)
- **`test_map` 은 facade 패턴에서 false negative 를 낸다 (9/14 mhctools 스모크 결과).** mhctools 는 `__init__.py` 에서 `NetMHCpan` 등을 re-export 하는 구조인데, 테스트는 `from mhctools import NetMHCpan` 로 씀. test_map 이 import 경로 기반 매칭이라 `netmhc_pan.py` 는 놓치고 `__init__.py` 만 연결됨. 21개 미연결 중 **16개(76%)가 실제로는 `tests/test_*.py` 가 존재**. 원 설계는 이 한계를 인지해 "**직접 연결된 근거를 찾지 못했다**" 문구를 쓰므로 표현은 안전. 다만 실무 저장소가 facade 를 흔히 쓰므로 PHASE 6·7 report 에서 이 한계를 명시적으로 언급하거나, `__init__.py` 의 re-export 를 역추적하는 개선을 고려. **진짜 테스트 없음은 5개** (`common.py`, `netmhc3.py`, `netmhc4.py`, `cleanup_context.py`, `input_file_formats.py`) — mhctools 실질 test coverage 는 68/73 (93%)

## Known Problems

- **팀 공용 키의 Gemini 무료 할당량 소진 (9/14).** 소진된 모델: `gemini-3.8-flash`, `gemini-flash-latest`, `gemini-3.6-flash`. 원인은 초기 실행에서 요청 간격 없이 25건을 연속 호출한 것. 현재 스크립트는 7초 간격 + 429시 65초 백오프 적용됨.
  - **할당량은 키(프로젝트) 단위이고, 같은 키 안에서도 모델별로 따로 걸린다.**
  - 사용자 개인 키를 새로 발급해 `.env`의 `GEMINI_API_KEY`를 교체하여 해소함. 팀원 로컬 `.env`는 그대로이므로 팀원은 리셋까지 위 모델들을 못 씀
- **`gemini-2.5-flash`는 신규 사용자에게 막힘.** 404와 함께 `gemini-3.6-flash` 사용 권고 메시지 반환. `judge/llm.py`는 3.6-flash 이상을 기준으로 작성할 것
- **참고 문서 2개가 저장소에 없음.** `ReCode_개발환경_및_세부실행계획.md`, `ReCode_개발계획서.md`. `CLAUDE.md`가 참조하는데 로컬에도 git에도 없음. 현재 사용 중인 사본(`Downloads\`)은 **Gemini 전환 전 판본** — 1.3절이 아직 "Claude API / OpenAI embedding", 290줄이 "console.anthropic.com", 3절 트리에 `analyzer/ # A 담당` 주석이 남아 2절 "폴더 분업을 두지 않는다"와 모순. 갱신 후 커밋 필요
- `ReCode_개발계획서.md` 7.2절 500자 심사 폼 답변, 4절 아키텍처 설명에 "Claude API" 표현 잔존. 갱신 필요
- 1차 사이클의 검증 샘플·결과 원본이 저장소 밖(`Downloads\ReCode_*.txt`)에 있어 릴레이로 전달되지 않음. `cache/` 는 gitignore 대상이라 재실행해도 커밋되지 않음. 판정 근거 원본을 팀이 공유해야 한다면 별도 위치를 정해야 함 (결론과 수치는 본 STATUS.md에 기록됨)
- `scripts/` 는 3절 프로젝트 구조에 없는 디렉터리다. 제품 코드(`analyzer/` · `judge/`)가 아니라 PHASE 1 검증 도구라 분리했음
- **venv 드리프트는 개발자별로 다르다 (9/15 실측으로 정정).** `.venv/` 는 gitignore 대상이라 각자 별개다.
  - **사용자 PC (9/15 실측)**: `anthropic`·`openai` **없음**(`e5bee20` 의 `pip uninstall` 은 실제로 실행됐고 `Successfully uninstalled` 확인됨), `sentence-transformers 6.0.1`·`torch 2.14.0`·`google-genai 2.23.0` **있음**. `requirements.txt` 와 일치. 정리할 것 없음
  - **팀원 PC**: `anthropic`·`openai` 가 남아 있고 `sentence-transformers` 가 없다고 보고됨. 이는 `e5bee20` 이후 `pip install -r requirements.txt` 를 다시 돌리지 않아 생긴 상태로 보인다
  - **해야 할 일은 `pip uninstall` 이 아니라 팀원 venv 재설치**:
    ```powershell
    pip install -r requirements.txt
    pip uninstall anthropic openai -y   # 남아 있는 잔여분만 제거
    ```
  - ⚠️ **팀원 PC 에서 `pip freeze > requirements.txt` 를 돌리면 안 된다.** 그 venv 에는 `sentence-transformers` 스택이 없어서 requirements 에서 지워진다. 재설치 후에만 freeze 할 것
- **`google-genai` 하위 패키지는 `requirements.txt` 에 이미 들어 있다 (9/15 실측으로 정정).** `google-auth==2.58.0`, `cryptography==50.0.1`, `distro==1.9.0`, `pyasn1==0.6.4`, `pycparser==3.0`, `tenacity==9.1.4` 모두 존재. `e5bee20` 의 `pip freeze` 에 포함됐음. 조치 불필요

## 다음 사람이 알아야 할 도구 특성

- **vulture는 후보를 찾으면 exit 3을 낸다** (1이 아님). `ExitCode(NoDeadCode=0, InvalidInput=1, InvalidCmdlineArguments=2, DeadCode=3)`. exit 1은 문법 오류 파일만 건너뛰고 나머지 스캔은 계속되므로 실패로 처리하면 안 됨
- **Windows 콘솔 인코딩**: Python이 stdout을 cp949로 씀. JSON을 파일로 리다이렉트하면 한글이 cp949로 저장됨. PowerShell 화면 출력은 정상
- `python-dotenv`의 `load_dotenv()`는 **스크립트 파일 위치**에서 위로 올라가며 `.env`를 찾는다. 저장소 밖 스크립트에서는 경로를 명시해야 함
- `analyzer/test_map.py`는 `static_check.py`의 `EXCLUDE_DIRS`·`iter_python_files`를 import한다. 3절 구조가 공용 util 파일을 허용하지 않아 모듈 간 import로 처리함
- `high_churn()`의 출력 키는 16.1이 정한 `commits_60d` 고정. `days` 인자를 바꿔 부르면 키 이름과 실제 창이 어긋남
- **대형 저장소에서 2,000개 상한은 "파일 수"를 크게 줄인다.** django 실측에서 py 2,616파일 중 **15개 파일만 남았다.** 커밋 최상위 파일들이 각각 함수를 수백 개씩 갖고 있기 때문. 15절 규칙("commit 빈도 높은 파일부터 남긴다") 그대로의 동작이지만, 인수인계 관점에서 넓게 훑기보다 깊게 파는 선택이다. PHASE 9에서 대형 저장소를 다룰 때 이 트레이드오프를 재검토할 것
- `judge/extract.py` 는 `analyzer/collect.py`(`CollectError`)와 `analyzer/test_map.py`(`commit_counts`)를 import 한다. 파이프라인 순서가 collect → extract 라 방향은 단방향이며 순환하지 않음
- **큰 저장소 clone 은 체크아웃이 끝나기 전에 `.git/HEAD` 가 먼저 생긴다.** clone 완료 판정에 `.git/HEAD` 존재를 쓰면 안 된다(django 실측에서 경합 발생, `git log` 가 `your current branch appears to be broken` 로 실패). `git rev-parse HEAD` 성공 여부로 판정할 것
- `repos/` 는 gitignore 대상이지만 디스크를 많이 쓴다. django 클론 하나가 약 180MB

## 참고 규약

- 세션 시작 전 `git pull`, 종료 전 `git push`
- 새 패키지 설치 시 즉시 `pip freeze > requirements.txt` 커밋
- 세부 규약은 `CLAUDE.md` / `AGENTS.md`
