# Re:Code Handoff

> `team-recode/recode` · main · `ac8410c` · 커밋 29개

이 문서는 코드를 설명하지 않는다. **수정 전에 확인해야 할 것**만 모았다.
모든 항목에는 코드 근거가 붙어 있다. 근거가 없는 항목은 만들지 않았다.

## 1. Repository overview

- 저장소: `team-recode/recode`
- 기준 커밋: `ac8410c` (`main`)
- 전체 커밋: 29개

## 2. Before you touch this repo

### 1. `analyze.py`

Evidence:
- 최근 60일간 2회 변경 (마지막 2026-09-16)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

### 2. `app/main.py`

Evidence:
- 최근 60일간 2회 변경 (마지막 2026-09-16)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

### 3. `judge/llm.py`

Evidence:
- 최근 60일간 2회 변경 (마지막 2026-09-15)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

### 4. `judge/report.py`

Evidence:
- 최근 60일간 2회 변경 (마지막 2026-09-16)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

### 5. `analyzer/__init__.py`

Evidence:
- 최근 60일간 1회 변경 (마지막 2026-09-12)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

## 3. Questions for the previous developer

1. 두 클라이언트 생성 함수에서 API 키가 없을 때 발생하는 예외 타입과 genai 임포트 위치를 다르게 설계한 이유가 무엇인가요?
   - 근거: `scripts/run_validation.py:60`, `judge/llm.py:161`
   - 확인된 사실: 함수 A(scripts/run_validation.py)는 SystemExit을 발생시키고 모듈 상단에서 genai를 임포트하는 반면, 함수 B(judge/llm.py)는 CollectError를 발생시키고 함수 내부에서 genai를 임포트합니다.

2. 두 진입점에서 예외 발생 시 출력하는 접두사 메시지를 다르게 설정한 이유가 무엇입니까?
   - 근거: `analyzer/collect.py:102`, `analyzer/static_check.py:146`
   - 확인된 사실: analyzer/collect.py의 main 함수에서는 예외 발생 시 "수집 실패: {exc}"로 출력하는 반면, analyzer/static_check.py의 main 함수에서는 "정적 분석 실패: {exc}"로 출력합니다.

3. 두 함수에서 테스트 파일과 제외 대상을 판별하는 조건이 서로 다른 이유는 무엇인가요?
   - 근거: `judge/extract.py:34`, `scripts/make_samples.py:65`
   - 확인된 사실: judge/extract.py의 is_test_file은 rel.name == "conftest.py"와 "tests/" 경로를 판별하며 setup.py를 포함하지 않지만, scripts/make_samples.py의 is_test_file은 rel.name in ("setup.py", "conftest.py")를 포함하고 경로 검사 조건에서 차이가 있습니다.

4. 왜 작업이 완료되지 않았을 때 report_page는 리다이렉트하고 get_report는 예외를 발생시키는지 궁금합니다.
   - 근거: `app/main.py:256`, `app/main.py:261`
   - 확인된 사실: report_page 함수는 작업이 완료되지 않은 경우 RedirectResponse를 반환하지만, get_report 함수는 409 HTTPException을 발생시킵니다.

5. 독스트링 제거 시 _normalize 함수는 작은따옴표 삼중 따옴표도 처리하는데 normalize 함수는 큰따옴표 삼중 따옴표만 처리하도록 의도하신 이유가 있나요?
   - 근거: `judge/embed.py:57`, `scripts/make_samples.py:70`
   - 확인된 사실: _normalize 함수는 큰따옴표와 작은따옴표 삼중 따옴표를 모두 처리하는 반면, normalize 함수는 큰따옴표 삼중 따옴표만 처리하도록 구현되어 있습니다.

## 4. High-change areas

최근 60일간 반복적으로 변경된 영역이다. 변경 횟수는 git 이력에서 센 수치다.

| 파일 | 60일 변경 | 마지막 변경 |
|---|---|---|
| `scripts/run_validation.py` | 3 | 2026-09-15 |
| `analyzer/collect.py` | 1 | 2026-09-14 |
| `analyzer/static_check.py` | 1 | 2026-09-14 |
| `app/__init__.py` | 1 | 2026-09-12 |
| `app/db.py` | 1 | 2026-09-16 |
| `judge/__init__.py` | 1 | 2026-09-12 |
| `judge/embed.py` | 1 | 2026-09-15 |
| `judge/extract.py` | 1 | 2026-09-15 |
| `scripts/__init__.py` | 1 | 2026-09-14 |
| `scripts/check_models.py` | 1 | 2026-09-14 |

그 외 2개 파일.

## 5. Test evidence gaps

직접 연결된 테스트 근거를 찾지 못했습니다. 테스트가 없다는 뜻은 아니다.

| 파일 | 전체 커밋 |
|---|---|
| `app/__init__.py` | 1 |
| `app/db.py` | 1 |
| `judge/__init__.py` | 1 |
| `judge/embed.py` | 1 |
| `judge/extract.py` | 1 |
| `scripts/__init__.py` | 1 |
| `scripts/check_models.py` | 1 |
| `scripts/label_sheet.py` | 1 |

## 6. Dead-code candidates

정적 호출 경로에서 사용 근거를 찾지 못했습니다. 삭제를 권하는 것이 아니라 확인이 필요한 후보다.

| 위치 | 이름 | 종류 | confidence |
|---|---|---|---|
| `app/main.py:77` | `cls` | variable | 100% |
| `app/db.py:32` | `RUNNING_STATUSES` | variable | 60% |
| `app/main.py:75` | `_check_url` | method | 60% |
| `app/main.py:119` | `health` | function | 60% |
| `app/main.py:126` | `landing` | function | 60% |
| `app/main.py:131` | `submit` | function | 60% |
| `app/main.py:146` | `progress_page` | function | 60% |
| `app/main.py:159` | `report_page` | function | 60% |
| `app/main.py:185` | `download` | function | 60% |
| `app/main.py:205` | `create_analysis` | function | 60% |

그 외 3개 후보.

## 7. First week

1. `analyze.py` 의 변경 이력을 읽고, 연결된 테스트가 정말 없는지 확인한다 (최근 60일 최다 변경 + 테스트 근거 없음)
2. 이전 개발자에게 물어볼 것: 두 클라이언트 생성 함수에서 API 키가 없을 때 발생하는 예외 타입과 genai 임포트 위치를 다르게 설계한 이유가 무엇인가요?
3. `app/main.py:77` 의 `cls` 이 실제로 쓰이지 않는지 확인한다 (정적 분석으로는 호출 근거를 찾지 못함)
