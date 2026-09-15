# Current Status

**Updated: 2026-09-16 (화) — PHASE 10·11 완료. 웹에서 URL 입력 → 진행 → 보고서까지 동작. 다음은 PHASE 12 (자기참조 데모)**

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

### PHASE 8 — CLI MVP 완성 (9/15)

`analyze.py` (저장소 루트). 20절대로 **웹 없이 한 명령으로 제품 핵심이 동작한다.**

```powershell
py analyze.py https://github.com/psf/requests
```

실측 출력 — 20절 예시 형식 그대로:
```
[1/5] 저장소 수집: https://github.com/openvax/mhctools
      openvax/mhctools 커밋 626개, head 529a8f7 (0.9초)
[2/5] 함수 추출 및 유사 후보 축소 (threshold 0.8)
      함수 631개 -> 후보 100쌍 (1.8초)
[3/5] LLM 판정 (gemini-3-flash-preview, 후보 8쌍, 전체 100쌍 중 --limit)
      finding 5건 / SKIP 3 / 폐기 0 / 오류 0 (3.0초)
[4/5] 정적 근거 수집 (High-Churn / Dead-Code / Test Gap)
[5/5] HANDOFF.md 생성  101줄 / 섹션 7개

Analysis complete.
Report: outputs/openvax__mhctools/HANDOFF.md
```

**옵션**
- `--skip-llm` — LLM 없이 정적 근거(③④⑥)만으로 보고서 생성. **quota 가 죽어도 제품이 돌아간다.**
  13.5절 "축소" 시나리오의 출력과 같다. psf/requests 실측 4단계 7초
- `--limit=N` — 후보 N개만 판정. quota 절약용
- `--model=이름` — quota 소진 시 교체 (모델별 quota 독립)
- `--threshold=0.80` — 유사도 하한

**산출물**: `outputs/{owner}__{repo}/` 에 `HANDOFF.md` · `pairs.json` · `findings.json`.
중간 산출물을 남기는 이유는 PHASE 9 품질 검증에서 단계별로 되짚어야 하기 때문이다.
`outputs/` 는 `.gitignore` 에 추가했다 (분석 대상은 남의 저장소이고 매번 재생성되는 artifact).
**PHASE 12 자기참조 데모 결과는 따로 저장할 위치를 정해야 한다** — 그건 커밋 대상이다.

**20절 "이 단계 완료 전 금지" 준수**: Tailwind·랜딩·리더보드·배지·발표영상·DB 모델링 전부 손대지 않음.

### PHASE 9 — 0단계 계측 도구 (9/15)

21절이 요구하는 측정 항목 중 기록되지 않던 것들을 채웠다. **LLM 호출 없이 완료.**

- **`analyze.py` 가 `outputs/{repo}/metrics.json` 을 쓴다.** 21절 측정 항목 전부:
  clone/analysis/embed/llm/static 시간, 함수 수, 후보 수, 판정 수, **실제 API 호출 수와 캐시 히트 수를 분리**,
  토큰 수, 비용(무료 티어 $0), finding/skip/폐기/오류 건수
- **`judge/llm.py` 가 `api_calls` · `cache_hits` · `tokens` 를 집계한다.** 이전에는 캐시 히트와 실제 호출이
  구분되지 않아 21절의 "LLM calls" 를 잴 수 없었다. `ask()` 가 `usage_metadata.total_token_count` 도 함께 반환
- **`scripts/label_sheet.py`** — 21절 사람 평가용. `make` 로 채점표를 만들고 `count` 로 집계한다.
  자동 채점이 아니다. 라벨은 사람이 적는다
  ```powershell
  py -m scripts.label_sheet make outputs/psf__requests/findings.json cache/label_requests.txt
  py -m scripts.label_sheet count cache/label_requests.txt
  ```
  대소문자·앞뒤 공백을 허용하고, 목록에 없는 값은 조용히 넘기지 않고 "알 수 없는 값" 으로 보고한다

**실측 예시** (mhctools, 전부 캐시 히트):
`clone 0.7초 / 전체 9.2초 / 함수 631개 / 후보 100쌍 / 판정 8쌍 / API 0회 · 캐시 8회 / finding 5건`

**PHASE 9 측정 대상 실측 규모** (LLM 없이 측정 완료):

| 저장소 | 급 | 함수 | 필터 통과 | 후보(=LLM 호출 수) |
|---|---|---|---|---|
| `psf/cachecontrol` | 소형 | 232 | 67 | **9** |
| `psf/requests` | 중형 | 711 | 235 | **35** |
| `openvax/mhctools` | 중형 | 1,814 | 631 | **100** |
| `django/django` | 대형 | 2,000 | 986 | **100** |

### PHASE 9 — 1단계 측정 실행 (9/15). **오늘 quota 소진, 일부 남음**

**무료 티어 한도를 정확히 확인했다.** 429 응답의 상세:
```
quotaId    : GenerateRequestsPerDayPerProjectPerModel-FreeTier
quotaValue : 20
```
**모델당·프로젝트당 하루 20회.** 쓸 수 있는 모델 4개 기준 하루 최대 80회.
전수 판정은 229회라 3일이 필요해 **저장소당 표본 20 으로 축소**했다(21절이 "샘플 수가 작으면 내부 검증으로 표현"을 허용).
`metrics.json` 에 `candidate_pairs` 와 `judged_pairs` 가 모두 남으므로 표본이라는 사실이 숨겨지지 않는다.

**측정 결과 (21절 항목)**

| 저장소 | 급 | 모델 | 함수 | 후보 | 판정 | finding | SKIP | 오류 | 분석(초) |
|---|---|---|---|---|---|---|---|---|---|
| `psf/cachecontrol` | 소형 | gemini-3.6-flash | 67 | 9 | **9 (전수)** | 3 | 6 | 0 | 151.6 |
| `psf/requests` | 중형 | gemini-3.5-flash | 235 | 35 | 20 (표본) | 11 | 9 | 0 | 419.5 |
| `openvax/mhctools` | 중형 | gemini-3-flash-preview | 631 | 100 | 11 (표본) | 7 | 3 | 1 | 141.3 |
| `django/django` | 대형 | gemini-3.1-flash-lite | 986 | 100 | 20 (표본) | 10 | 10 | 0 | 287.1 |

- **판정 60쌍 → finding 31건 (KEEP율 52%)**, 토큰 89,496, **비용 $0** (무료 티어)
- **평균 분석 시간 249.9초.** 대부분이 LLM 대기(요청 간격 7초 + 응답 지연)이고, 정적 분석은 django 82초가 최대
- **대형 저장소에서 실패하지 않음 (21절 목표 4번 확보)** — django 986함수·후보 100쌍·**오류 0**
- 18절 API 실패 대응이 실전 검증됨: 503/429 가 나도 나머지 후보를 계속 처리하고 보고서까지 완주
  (cachecontrol 1차 시도에서 503 3건 발생 → 재시도로 회복, 완주)
- `mhctools` 는 quota 롤링 제한으로 11쌍에서 중단. `judged_pairs: 11 / candidate_pairs: 100` 으로 기록되어 표본임이 드러난다

**quota 창은 자정 고정이 아니라 롤링이다.** 소진된 모델이 수십 분 뒤 일부 회복되는 것을 반복 관측했다.
다만 회복분이 적어(3건 수준) 연속 작업에는 쓸 수 없다. 모델을 갈아타는 쪽이 실무적이다.

**모델이 바뀌면 정밀도가 달라진다 — 측정에서 드러난 사실.**
`gemini-3.5-flash` 는 requests 에서 finding 11건 중 **3건이 "HTTP 메서드 이름 대소문자 불일치"** 였다.
이는 PHASE 1 에서 이미 오탐으로 확인된 건이다(`models.py:471`·`sessions.py:542` 의 `.upper()` 로 정규화되어 무의미).
같은 상황에서 `gemini-3-flash-preview` 는 PHASE 6 에서 SKIP 했다.
**모델 선택이 정밀도에 직접 영향을 준다.** 저장소마다 모델이 다르므로 저장소 간 유용률 비교는 교란되어 있다.
`metrics.json` 의 `model` 필드에 기록됨.

### PHASE 9 사람 라벨링 — 방향 변경 (2026-09-15 오후)

정식 사람 평가는 원 계획대로 **PHASE 13 (개발자 3~5명 외부 검증, 9/17~18)** 에서 수행. 오늘은 데모 저장소 선택과 오탐 유형 파악을 위한 **AI 소스 검증 baseline** 만 실행.

**총계 (n=31, AI 초안 + 소스 근거 재검토)**: useful 21 (68%) / ambiguous 2 (6%) / not_useful 8 (26%)

| 저장소 | useful | ambiguous | not_useful | 유용률 |
|---|---|---|---|---|
| cachecontrol (3) | 3 | 0 | 0 | 100% |
| mhctools (7) | 5 | 2 | 0 | 71% |
| django (10) | 7 | 0 | 3 | 70% |
| requests (11) | 6 | 0 | 5 | 55% |

**데모 저장소 후보 (PHASE 16 용)**: `mhctools` 유력. 유용률·규모 균형 + 도메인 특화로 데모 스크립트 짜기 좋음. `cachecontrol` 은 유용률 100%지만 표본 3건이라 작음, `requests` 는 대소문자 오탐 코퍼스 편향으로 유용률 저조.

**데모용 강한 finding 후보 2개** (잠재 버그성):
- `cachecontrol [02]`: `_load_from_cache:152` 는 `request.url` raw, 같은 클래스의 `cached_request:175` 는 `self.cache_url()` 로 정규화. URL 처리 불일치 → 캐시 쓰기/읽기 mismatch 가능성
- `requests [08]`: `_find` 는 None-value 쿠키 반환, `_find_no_duplicates` 는 None 이면 KeyError. 반환 타입 힌트 차이가 **실제 동작 divergence** 를 정확히 반영

**오탐 8건 유형 분류 (프롬프트 개선 재료, 재튜닝은 제출 후로 이관)**:
1. **컨텍스트 부재 (5건, requests [01]~[05])**: 함수 두 개만 잘라 던져 `.upper()` 정규화·`setdefault(..., 기본값)` 방어 코드를 못 봄. 이미 "설계에 반영해야 할 발견" 첫 항목으로 기록된 원칙의 재확인
2. **스타일 필터 누락 (2건, django [08][09])**: 18절 규칙 10 이 f-string vs %, 기본값과 동일한 값의 명시적 전달을 걸러내지 못함
3. **클래스 성격 판정 부재 (1건, django [05])**: QuerySet(쿼리 래퍼)/Model(도메인 인스턴스) 근본 성격이 다른데 `__repr__` 차이를 finding 으로 만듦

**ambiguous 2건**: mhctools `[03][05]` — 같은 "버전별 default mode" 패턴이 3번 노출된 것 중 뒤 2건. 리포트 계층의 묶기(合并) 로직이 raw 3건 → 리포트 1건으로 압축하므로 사용자 경험에서는 문제 없음. **묶기가 실제로 필요한 이유의 근거**.

**라벨 시트 상태**: `evaluation/라벨_*.txt` 4개에 AI 초안 라벨이 로컬에 채워진 상태(`git status` modified). **커밋 안 함** — PHASE 13 정식 라벨링이 심사 폼 근거이므로 그때 빈 시트로 재시작. 로컬 유지는 사용자 참고용. 실수 커밋 방지 원하면 `git restore evaluation/라벨_*.txt`.

> `evaluation/` 은 3절 구조에 없는 디렉터리다. **PHASE 13 결과가 심사 폼 정식 근거.** 오늘 AI baseline 은 데모 저장소 선택 · 오탐 유형 파악용 내부 자료.

### PHASE 10 — FastAPI 연결 (9/16)

`app/db.py` 신규, `app/main.py` 확장, `analyze.py` 에 진행 콜백 추가. 22절 스펙대로.

**엔드포인트 3개 실측 통과**

| 요청 | 결과 |
|---|---|
| `POST /api/analyze` | `{"job_id": "ea43f66c..."}` |
| `GET /api/jobs/{id}` | `{status, progress, repo_url, created_at, error?}` |
| `GET /api/jobs/{id}/report` | `HANDOFF.md` 본문 (text/plain) |

**`jobs` 테이블 1개.** 22절이 "복잡하게 만들지 않는다" 고 해서 컬럼 7개만 둠:
`id / repo_url / status / progress / result_path / error / created_at`. 마이그레이션 도구 없이 `create_all`.

**상태 9개** — 22절 목록 그대로. 실제 파이프라인 순서에 맞춰 발행:
`queued → cloning(5) → extracting(15) → embedding(35) → judging(40) → static_analysis(88) → generating_report(95) → completed(100)`, 실패 시 `failed`.

**파이프라인을 복제하지 않고 콜백을 넣었다.** `analyze.run(..., on_progress=fn)` 을 추가해
워커가 단계마다 `jobs` 행을 갱신한다. 웹용 파이프라인을 따로 만들면 CLI 와 어긋난다.
상태 문자열은 22절 이름을 그대로 쓰므로 워커는 받은 값을 그대로 DB 에 넣는다.

**큐를 두지 않았다.** 1.4절 결정(Celery/Redis 제외) 대로 FastAPI `BackgroundTasks` + `jobs` 테이블로 처리.

**`result_path` 만 저장한다.** `HANDOFF.md` 는 이미 `outputs/` 에 있으므로 본문을 DB 에 중복 저장하지 않는다.

**실측 검증 (LLM 호출 0회, `skip_llm=true` 로 quota 미사용)**
- 정상: cachecontrol → `completed` 100%, 보고서 76줄 수신
- 잘못된 URL: `POST` 단계에서 **422** 로 거부. job 자체를 만들지 않는다
  (초기 구현은 500 이었다. `CollectError` 가 `ValueError` 가 아니어서 pydantic 이 422 로 바꾸지 못함 → 검증기에서 `ValueError` 로 변환)
- 없는 저장소: `failed` 상태 + `error` 에 `CollectError: git clone 실패 (exit 128)` 원문 보존
- 진행 중 보고서 요청: **409** + `"아직 분석 중입니다. status=cloning, progress=5"` (빈 보고서를 주지 않는다)
- 없는 job: **404**

**캐시가 더워지면 앞 단계가 순식간에 지나간다.** clone·임베딩이 캐시면 `cloning`~`embedding` 이
2초 폴링에 안 잡히고 `static_analysis` 부터 보인다. 버그가 아니다. PHASE 11 진행 화면에서
SSE 로 바꾸면 모든 단계가 보인다.

### PHASE 11 — 결과 화면 (9/16)

23절 3화면 완성. Tailwind CDN + Jinja2 + SSE(`sse-starlette`). **빌드 스텝 없음.**

| 화면 | 경로 | 내용 |
|---|---|---|
| Landing | `GET /` | 한 줄 설명("코드는 남지만, 이유는 남지 않습니다"), URL 입력, Analyze, 예제 저장소 3개 |
| Progress | `GET /jobs/{id}` | SSE 로 6단계 진행 표시 + 진행 바 |
| Report | `GET /jobs/{id}/report` | Before you touch this repo(주인공) / First week / High-change / Test gaps / Dead-code |

추가 경로: `POST /analyze`(폼), `GET /jobs/{id}/download`(HANDOFF.md), `GET /api/jobs/{id}/stream`(SSE), `GET /health`.
기존 `/` 의 헬스체크는 `/health` 로 옮겼다(랜딩이 `/` 를 차지).

**`judge/report.py` 에 `gather_evidence()` 를 뺐다.** 마크다운(`build()`)과 웹 화면이 **같은 데이터**를 쓴다.
두 곳에서 각자 계산하면 문서와 화면이 어긋난다. `first_week` 계산도 여기로 옮겼다.
리팩터링 후 기존 `HANDOFF.md` 와 출력이 **바이트 단위로 동일**함을 회귀 확인.

**23절 UX 원칙 준수**
- 코드 품질 점수 없음. "위험"·"나쁜 코드" 표현 없음
- Dead-code 는 "삭제를 권하는 것이 아니라 확인이 필요한 후보", Test gap 은 "테스트가 없다는 뜻은 아닙니다" 로 표기
- finding 카드는 23절이 정한 네 가지를 모두 노출: 제목 / 물어볼 질문 / 코드에서 확인된 사실 / 근거(`파일:줄`)
- Markdown 복사 버튼 + `HANDOFF.md` 내려받기

**실측 검증 (LLM 호출 0회, `skip_llm` 사용)**
- Landing: 한 줄 문구·Analyze·예제 3개 모두 렌더
- 잘못된 URL 폼 제출 → **400 + 랜딩에 오류 메시지** (API 경로는 422 JSON, 폼은 화면으로 돌려준다)
- 정상 제출 → **303** → Progress → 완료 후 Report 자동 이동
- SSE 실측: `cloning(5) → extracting(15) → static_analysis(88) → completed(100) → done`
- Report: 5개 섹션 + 복사/다운로드 버튼 렌더, 다운로드 76줄 수신

**SSE 가 끊기면 폴링으로 내려앉는다.** 프록시 환경에서 스트림이 막히는 경우가 있어
`onerror` 에서 2초 폴링으로 전환한다(PHASE 14 배포 대비).

## In Progress

- PHASE 10·11 완료. **브라우저에서 URL 을 넣으면 보고서까지 나온다.** 다음은 **PHASE 12 (자기참조 데모, 24절)**
- PHASE 9 는 AI 소스 검증 baseline 까지. **정식 사람 평가는 PHASE 13 (9/17~18) 개발자 외부 검증**

## Next

**PHASE 10 — FastAPI 연결 (9/16, 팀원 세션)**
22절 스펙. 3개 endpoint (`POST /api/analyze`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/report`). `analyze.py` 를 래핑. job 상태 8개 (`queued` → `cloning` → ... → `completed`/`failed`). DB `jobs` 테이블 1개만 (id, repo_url, status, progress, result_path, error, created_at).

**PHASE 11 — 화면 3개 (9/16~17, 팀원 세션)**
23절. Landing / Progress (SSE) / Report. HANDOFF.md 렌더링 + Markdown copy/download.

**PHASE 12·13·14 — 9/17 병렬**
- 12: Re:Code 자기참조 데모 (Re:Code 를 Re:Code 로 분석, 24절)
- 13: 개발자 3~5명 사용자 테스트 (25절). **빈 라벨 시트 재배포** → useful/ambiguous/not_useful 라벨링. 심사 폼 정식 근거
- 14: Railway 또는 Render 배포 결정 및 실행 (26절)

**PHASE 15·16·17 — 9/18~19**
- 15: 심사 폼 500자 답변 갱신 (PHASE 13 결과 반영, 27절). **본안은 이미 500자 완성 (2026-09-15)**, PHASE 13 유용률만 추가 문장으로 삽입 예정
- 16: 데모 스크립트 · 영상 촬영 (28절) — **저장소 후보 비교 아래 참고**
- 17: 최종 제출물 정리 (29절)

### PHASE 16 데모 저장소 후보 비교 (2026-09-15 예비 조사)

**추천: `mhctools` (primary), `cachecontrol` (backup)**

| 저장소 | 유용률 | 규모 | 데모 강점 | 약점 |
|---|---|---|---|---|
| **mhctools** | 71% (5/7) | 631 함수, 100 후보 | 도메인 특화(MHC 예측) → "낯선 저장소" 서사 딱 맞음. T1/T2/T3 리콜 6/6 통과(PHASE 1). Static 근거 풍부 (High-Churn 20건, test coverage facade 한계 명시) | MHC 도메인 특수. 서브클래스 mode 차이 3건 개념 중복 |
| **cachecontrol** | 100% (3/3) | 232 함수, 9 후보 | 소규모라 데모 짧음(2분 이내). finding [02] 캐시 URL 정규화 불일치는 잠재 버그 강도 최상 | 3건뿐이라 "이게 다냐" 느낌. HTTP 캐싱 지식 필요 |
| django | 70% (7/10) | 986 함수 필터, 100 후보 | 규모 임팩트, 누구나 아는 저장소 | 2000 상한으로 15 파일만 남아 서사 애매. 답변에 Django 심층 지식 필요 |
| requests | 55% (6/11) | 235 함수, 35 후보 | 인지도 최고 | **not_useful 5건 노출 위험** (심사장 오탐 지적 방어 어려움). 대소문자 오탐 부적합 |

**데모용 강한 finding 후보 3개** (PHASE 16 스크립트 초안 재료):

1. **mhctools BigMHC `kind_support`** (`[02]`): base 클래스는 `self.mhc_class` 인스턴스 변수 사용, BigMHC 서브클래스는 `mhc_class='I'` 하드코딩. → "이게 의도된 제약(MHC-I 전용)인가 미구현인가"
2. **mhctools `predict_with_flanks` override** (PHASE 1 T1): base 는 flanks 를 검증만 하고 버림, mhcflurry override 는 flanks 를 predict 에 전달. → "base 가 인자를 무시하는 게 정상 동작인가"
3. **cachecontrol `_load_from_cache` vs `cached_request`** (`[02]`): 같은 `CacheController` 클래스에서 URL 처리가 불일치 (raw vs `self.cache_url()` 정규화). → "캐시 쓰기/읽기 mismatch 아닌가"

셋 다 **"코드만 봐선 답할 수 없고, 원저자에게 물어야 답이 나오는" 형태** → 제품 정의(인수인계 도구)에 정확히 부합.

**mhctools 를 primary 로 선택한 이유**: (1) 도메인 특화로 "낯선 저장소" 서사에 자연스러움, (2) 강한 finding 2개 확보 가능(BigMHC + PHASE 1 T1), (3) static 근거 다양(churn 20건 + facade 한계 명시로 도구 정직성 노출).

**cachecontrol 을 backup 으로 둔 이유**: mhctools 데모 준비 실패/시간 부족 시 대안. finding [02] 단일로 데모 가능(잠재 버그 강도 최상), 저장소가 작아 클론·분석 시간 총 3초 내외.

**PHASE 16 진입 시 다음 사람이 할 것**:
1. `py analyze.py https://github.com/openvax/mhctools --model=gemini-3-flash-preview --limit=20` (LLM 캐시 있어 quota 부담 낮음)
2. `outputs/openvax__mhctools/HANDOFF.md` 열어 finding 목록 확인
3. 아래 데모 스크립트의 강한 finding 3개가 실제 리포트에 있는지 확인 (없으면 fallback 결정)
4. 아래 스크립트 그대로 활용하거나 finding 위치·행 번호만 실측치로 갱신

### PHASE 16 데모 스크립트 초안 (2026-09-16 작성, 28절 6단계 매핑)

**총 시간 목표: 2~3분** (28절 원문). 시연은 라이브(실제 브라우저) 권장 — 화면 캡처보다 신뢰도 높음.

#### 시나리오 A — mhctools (primary)

**1. GitHub URL 입력**
```
https://github.com/openvax/mhctools
```
> "면역학 도메인의 MHC 예측 도구입니다. 심사위원 대부분이 처음 보는 저장소일 겁니다 — 이게 요점입니다."

**2. 실시간 분석** (SSE 로그 표시)
```
[1/5] Repository cloning...        openvax/mhctools (611 commits, ~2초)
[2/5] Extracting functions...      1,814 -> 631 filtered -> 100 candidates
[3/5] LLM judging...               11 pairs (finding 7 / skip 3 / error 1)
[4/5] Static evidence...           High-Churn 20 + Test gap 21
[5/5] Generating HANDOFF.md        7 sections
```
> "정적 근거는 즉시, LLM 판정은 후보 100쌍 중 표본 11쌍(quota 상한)입니다."

**3. 결과 — 첫 finding**
> **"BigMHC 서브클래스가 `mhc_class='I'` 로 하드코딩되어 있습니다."**
>
> 근거:
> - `mhctools/bigmhc.py:157` — `kind_support()` 가 `mhc_dependence='single_allele'`, `mhc_class='I'` 반환 (고정값)
> - `mhctools/wrapper_base.py:73` — 부모 클래스는 `self.mhc_class` 인스턴스 속성 사용

**4. 질문** (원저자에게 물어볼 형태)
> **"BigMHC 구현에서 `mhc_class='I'` 를 고정한 것이 의도된 제약(MHC-I 전용)인가요, 아니면 MHC class II 지원이 아직 미구현인가요?"**
>
> "이 도구는 잘못됐다고 말하지 않습니다. 원저자만 답할 수 있는 걸 원저자에게 물어볼 형태로 만듭니다."

**5. First week**
> **"변경이 잦고(`mhctools/__init__.py` 최근 60일 22회, 최상위) 테스트 근거가 부족한 예측기 등록 로직에 regression test 부터 추가하세요."**
>
> "새 predictor 추가마다 `__init__.py` 가 함께 바뀌는 패턴이 있어 회귀 위험이 큽니다."

**6. 자기참조 결과**
> "저희도 2주간 AI로 만들었습니다. **저희 자신의 저장소에도 Re:Code 를 돌린 결과를 함께 제출합니다.**"
>
> (Re:Code → Re:Code 인수인계서 링크 클릭 → 첫 finding 노출)

**mhctools 를 primary 로 쓰는 이유** (28절 조건 대조):
- ✅ 유사 로직 + 의미 있는 차이 (BigMHC override, predict_with_flanks override)
- ✅ high churn (`__init__.py` 60일 22회)
- ✅ test evidence gap (facade 패턴으로 21건 미연결)
- ✅ dead code (39건)
- 조건 2개 이상 통과 요건 초과 달성 (4개 통과)

#### 시나리오 B — cachecontrol (backup)

**시간 부족 · mhctools 준비 실패 시 대안.** 저장소가 작아 데모 전체 2분 이내 가능. finding [02] 단일로 강한 인상.

**1. GitHub URL 입력**
```
https://github.com/psf/cachecontrol
```
> "HTTP 캐시 미들웨어입니다. 소규모지만 실서비스에서 널리 쓰입니다."

**2. 실시간 분석**
```
[1/5] Repository cloning...        psf/cachecontrol (~1초)
[2/5] Extracting functions...      232 -> 67 filtered -> 9 candidates
[3/5] LLM judging...               9 pairs (finding 3 / skip 6)
[4/5] Static evidence collection...
[5/5] Generating HANDOFF.md        4~5 sections
```
> "전수 9쌍 판정, 전부 완주."

**3. 결과 — 첫 finding (잠재 버그 강도)**
> **"같은 클래스 안에서 캐시 URL 처리 방식이 불일치합니다."**
>
> 근거:
> - `cachecontrol/controller.py:152` — `_load_from_cache` 가 `request.url` 을 raw 로 사용
> - `cachecontrol/controller.py:175` — `cached_request` 는 같은 클래스에서 `self.cache_url()` 로 정규화

**4. 질문**
> **"`_load_from_cache` 가 URL 정규화 없이 `request.url` 을 직접 캐시 키로 쓰는 것이 의도된 것인지, 아니면 `cached_request` 와 마찬가지로 `self.cache_url()` 정규화를 거쳐야 하는지 확인 부탁드립니다."**
>
> "후자라면 캐시 쓰기/읽기 mismatch 로 캐시 미스가 조용히 발생할 수 있습니다."

**5. First week**
> **"먼저 위 URL 정규화 지점을 확인하세요. `cached_request` · `_cache_set` 는 모두 정규화를 거치지만 `_load_from_cache` 만 raw URL 을 씁니다. 원저자 확인 후 실측 캐시 히트율을 로그로 재보세요."**

**6. 자기참조 결과**: 시나리오 A 와 동일

#### 촬영 · 시연 시 주의

- **라이브 시연 권장** (녹화 재생보다 신뢰도 ↑). quota 있으면 캐시 히트로 실행 시간 짧아짐
- **분석 화면**: SSE 로그가 실시간으로 흐르는 순간 강조 (진행률 아니라 로그 내용 보이게)
- **결과 화면**: HANDOFF.md 의 "물어볼 질문" 섹션 확대. 근거 파일:줄 표시가 클릭 가능하면 GitHub 링크로 이동 데모까지
- **BGM 없이 나레이션만**. 심사위원이 finding 을 실제로 읽을 시간 확보
- **하지 말 것**: "정확도 N%" 주장 (21절 정확도 과장 금지 원칙). "저희 도구는 이런 걸 발견합니다" 정도의 서술

#### PHASE 16 진입 전 확인 사항 (실측)

- [ ] mhctools finding [02] BigMHC kind_support 가 실제 리포트에 있는지 확인 (없으면 다른 강한 finding 으로 대체)
- [x] **mhctools `__init__.py` High-Churn 22회 최신 실측 확인 (2026-09-16)** — `analyzer.static_check` 재실행 결과 `commits_60d: 22`, `last_changed: 2026-09-13`. 데모 스크립트 수치 그대로 사용 가능
- [x] **mhctools test evidence gap 실측 (2026-09-16)** — `netmhc_pan.py` 커밋 38회+테스트 미연결, `netmhc_cons.py` 24회+미연결, `netmhc_pan28.py` 14회+미연결. facade 패턴 false negative 확인 (STATUS.md "설계에 반영해야 할 발견" 4번 그대로)
- [ ] cachecontrol finding [02] 가 실제 리포트에 있는지 확인
- [ ] 시연 URL 확정 (Railway or Render, PHASE 14 결정 후)

### PHASE 11 랜딩 페이지 문구 확정 (2026-09-16, 27절 원안 그대로)

**팀원이 PHASE 11 화면 개발 시 그대로 삽입.**

**대표 헤드라인 (Landing 최상단, 대안 2개 중 택)**:
- A) "코드는 남지만, 이유는 남지 않습니다." (23절 원안)
- B) "Before you touch the repo, know what to ask." (23절 원안)

**추천: A** (한국어, 문제 서사 즉시 전달, 7.1절 한 줄과 정합)

**Problem·Insight·Solution 3문장** (27절 원안, 심사 폼 답변과도 정합):

**Problem** (문제)
> AI가 코드를 쓰는 속도는 빨라졌지만, 그 코드를 이해하는 속도는 빨라지지 않았습니다.

**Insight** (통찰)
> 코드는 무엇을 하는지는 보여주지만, 다음 개발자가 무엇을 확인해야 하는지는 알려주지 않습니다.

**Solution** (해결)
> Re:Code는 저장소의 코드와 변경 이력을 분석해, 다음 개발자가 손대기 전에 확인해야 할 맥락과 질문을 만들어줍니다.

**예제 저장소 (Landing 하단, 클릭 시 캐시된 결과)**:
- `psf/cachecontrol` (소형, 3건 강한 finding)
- `openvax/mhctools` (중형, 도메인 특화)
- `psf/requests` (대형이지만 인지도 최고)

원래 27절이 요구하는 "예제 repository 2~3개" 조건 충족. django 는 대형이라 시연 시간 문제로 제외.

**Landing UX 원칙 (23절)**:
- 서비스 한 줄 설명 + URL 입력창 + Analyze 버튼 (필수)
- 코드 품질 점수 전면에 두지 않음
- "위험", "나쁜 코드" 표현 금지
- 사용자가 다음 행동 알 수 있게

### PHASE 15·16 이미지 컨셉 초안 (2026-09-16 작성, 개발계획서 7.3절 대응)

**촬영 시점**: PHASE 11 완주 후(9/17 저녁~) + PHASE 14 배포 URL 확정 후. 지금은 컨셉·순서 확정만.

#### 대표 이미지 (심사 폼 필수, 문제를 한눈에)

**원칙 (7.3절 원안 유지)**: 서비스 스크린샷보다 **문제를 한눈에 보여주는 이미지**를 우선. 클릭 여부가 여기서 갈림.

**컨셉 후보 4개**:

| 후보 | 컨셉 스케치 | 헤드라인 | 강점 | 약점 |
|---|---|---|---|---|
| **A. 빈 자리와 물음표** | 왼쪽: 정돈된 코드 파일들 · 오른쪽: 빈 의자 + `?` · 중앙 화살표 "AI가 만들어 놓고 사라진 코드" | "AI가 쓴 코드는 아무도 읽은 적이 없습니다" | 문제 서사 즉시 전달. 7.1절 한 줄과 정합 | 제품 성격 안 보임 |
| B. 리뷰어 없는 코드 | 코드 diff 중앙, 리뷰어 자리에 빈 자리 + `?`, 커밋 히스토리에 AI 아이콘만 늘어섬 | "물어볼 사람이 없습니다" | 개발자 공감 강함 | 개발자 아닌 사람에겐 추상적 |
| C. 인수인계서 미리보기 | HANDOFF.md 의 "물어볼 질문" 섹션 확대 + 근거 링크 강조 | "다음 개발자가 물어볼 것을 대신 만듭니다" | 제품 결과 직관 | 제품 스크린샷이라 7.3절 원안과 어긋남 |
| D. 두 함수 대치 | 같은 이름·다른 로직 두 함수 · 화살표: "Re:Code가 발견" | "의도된 차이인가요?" | ①② 기능 강조 | 문제 서사 약함 |

**추천: A** — 7.3절 원안 방침 정합. 7.1절 한 줄 답변 "AI가 쓴 코드는 아무도 읽은 적이 없어서, 물어볼 사람조차 없습니다" 와 시각적으로 붙는다.

**대안: A + C 합성** — 상단(A 문제) + 하단(C 해결). 세로 분할. 시각적 정보량 많아 단순함은 잃음. **최종 결정은 실제 스케치 후**.

**제작 도구 후보**: Figma (무료) / Canva / PowerPoint. 스톡 이미지는 [unDraw](https://undraw.co) (오픈소스, 색 커스텀 가능). 시간 예산 1시간 이내.

#### 스크린샷 5장 순서

**원안 (7.3절)**: 리더보드 → 분석 진행 → 인수인계서 전체 → "물어볼 질문" 확대 → "첫 주에 할 일" 확대

**갱신 (2026-09-16)**: 리더보드 범위 제외(5.1 일정표 개정)로 순서 조정

| # | 화면 | 촬영 대상 | 강조 요소 |
|---|---|---|---|
| 1 | **Landing** | URL 입력창 + 예제 저장소 2~3개 | 한 줄 헤드라인 · Analyze 버튼 |
| 2 | **분석 진행 (SSE)** | 실시간 로그 흐르는 중간 상태 | 진행률보다 로그 내용(clone/extract/embed/judge) 보이게 |
| 3 | **인수인계서 전체** | HANDOFF.md 렌더링 전체 | 7개 섹션 구조 (또는 활성 섹션만) |
| 4 | **"물어볼 질문" 확대** | 3.Questions 섹션 close-up | 질문 문장 + 근거 파일:줄 링크 강조 |
| 5 | **"첫 주에 할 일" 확대** | 7.First week 섹션 close-up | 3개 action item + 각 근거 |

**촬영 조건**:
- **16:9 비율 필수** (심사 폼 규약)
- 해상도: 1920x1080 or 1280x720
- 브라우저 창 고정 (Chrome DevTools 로 viewport 크기 지정 가능)
- 라이트/다크 모드: 심사 폼 규약 확인 후 결정 (미확인 시 라이트 기본)
- **데모 저장소는 mhctools** (PHASE 16 primary 와 일치)

**촬영 도구**: Windows 11 Snipping Tool (Win+Shift+S) 로 지정 영역 캡처. 또는 브라우저 확장 (Awesome Screenshot 등).

**촬영 시점 결정 트리**:
```
PHASE 11 완주 (9/17 저녁) 됐나?
  YES → 로컬 스크린샷 촬영 가능
  NO → 촬영 대기
PHASE 14 배포 완료 (9/17) 됐나?
  YES → 배포 URL 스크린샷 (심사 진정성 ↑)
  NO → 로컬 스크린샷 사용
```

**심사 폼 진정성 관점**: 배포 URL 상태의 스크린샷이 로컬보다 강함 (심사위원이 URL 클릭해 실제로 접근 가능). 가능하면 9/18 아침에 배포 URL 확정 후 다시 촬영.

#### PHASE 16 진입 전 이미지 준비 체크리스트

- [ ] 대표 이미지 컨셉 A 스케치 1시간 (Figma or PowerPoint)
- [ ] Landing 페이지 완성 확인 (PHASE 11)
- [ ] 데모 저장소(mhctools) HANDOFF.md 실제 렌더링 확인
- [ ] 심사 폼의 이미지 규약(라이트/다크, 워터마크 여부) 재확인
- [ ] 스크린샷 5장 촬영 · 16:9 검증
- [ ] 대표 이미지 · 스크린샷 5장 심사 폼 업로드 시점 결정 (9/18 접수 전까지)

**부수 작업 (판정에 필수 아님)**:
- mhctools 표본 11 → 20 보강: quota 리셋 후
  ```powershell
  py analyze.py https://github.com/openvax/mhctools --model=gemini-3-flash-preview --limit=20
  ```
- ✅ `DEFAULT_MODEL` 갱신 완료 (9/14 저녁): `gemini-3-flash-preview` 로 고정
- ⏳ **팀원 PC 의 venv 드리프트 정리** (사용자 PC 는 9/15 실측으로 이미 정리됨). 팀원 세션 시작 시:
  ```powershell
  pip install -r requirements.txt
  pip uninstall anthropic openai -y
  ```
  ⚠ 팀원 PC 에서 `pip freeze > requirements.txt` 는 **금지** (sentence-transformers 스택 소실)

> `analyzer/`(③④⑥) + `judge/`(①②) + CLI(`analyze.py`) 가 모두 살아있는 상태. 이제 웹 계층(PHASE 10~11).


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
- **참고 문서 2개는 iCloud 에 있음.** `ReCode_개발환경_및_세부실행계획.md`, `ReCode_개발계획서.md` — `C:\Users\moonl\iCloudDrive\desktop\HAN\자격증, 대회 등\공모전\2026_원티드_AI_Championship\`. Gemini 전환은 반영됨(Claude/OpenAI 언급 0건 확인, 2026-09-15). 참고 문서 위치는 memory `reference_docs.md` 에 기록
- **`ReCode_개발계획서.md` stale 항목 정리 완료 (2026-09-16)**:
  - ✅ 4.1절 128행 · 7.4절 305행 `Spring Boot` → `FastAPI` 치환 (2026-09-15)
  - ✅ 7.2절 심사 폼 500자 답변에 PHASE 9 실측 수치 삽입 (finding 31건, django 986함수 무오류) — 정확히 500자 (2026-09-15)
  - ✅ 5.1 일정표 실제 진행 기준 재작성 (PHASE 0~17 매핑, 원안과 차이 명시)
  - ✅ 5.4 역할 릴레이 방식으로 재작성 (Claude Code=사용자, Codex=팀원, 폴더 소유권 없음)
  - ✅ 4.5절·7.3절 "9/15 배포" → "9/17 배포 (PHASE 14)" 갱신
  - ✅ 7.4 기술 스택 태그 실사용 기준으로 완전 재작성 (분석 파이프라인 + AI 개발 도구 분리, 심사 폼 선택 원칙 명시)
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
- **`print` 로 나가는 문자열에 em-dash(`—`, U+2014)를 쓰지 말 것.** cp949 로 인코딩되지 않아 `UnicodeEncodeError` 로 죽는다. 세 번 겪었다(`judge/llm.py`, `scripts/run_validation.py`, `scripts/label_sheet.py`). 쉼표나 하이픈으로 대체할 것. 독스트링·주석·파일에 쓰는 문자열은 UTF-8 이라 무해하다
- **파일에 쓴 JSON 을 다시 읽을 때 인코딩 주의.** `py -m ... > out.json` 으로 리다이렉트하면 cp949 로 저장되므로 `encoding='utf-8'` 로 읽으면 깨진다. 스크립트가 직접 `write_text(..., encoding='utf-8')` 로 쓴 파일은 정상
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
