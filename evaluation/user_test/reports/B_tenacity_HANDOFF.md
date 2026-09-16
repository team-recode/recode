# Re:Code Handoff

> `jd/tenacity` · main · `3e58094` · 커밋 615개

이 문서는 코드를 설명하지 않는다. **수정 전에 확인해야 할 것**만 모았다.
모든 항목에는 코드 근거가 붙어 있다. 근거가 없는 항목은 만들지 않았다.

## 1. Repository overview

- 저장소: `jd/tenacity`
- 기준 커밋: `3e58094` (`main`)
- 전체 커밋: 615개

## 2. Before you touch this repo

### 1. `tenacity/stop.py`

Evidence:
- 최근 60일간 1회 변경 (마지막 2026-08-05)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

### 2. `tenacity/asyncio/retry.py`

Evidence:
- 최근 60일간 1회 변경 (마지막 2026-08-05)
- 직접 연결된 테스트 근거를 찾지 못했습니다.

Why this matters:
- 자주 바뀌는데 직접 연결된 테스트 근거가 없다. 수정 시 회귀를 잡아줄 장치를 먼저 확인할 것

## 3. Questions for the previous developer

1. __and__에서는 self를, __rand__에서는 other를 대상으로 retry_all 여부를 검사하도록 서로 다르게 작성된 이유가 무엇인가요?
   - 근거: `tenacity/retry.py:42`, `tenacity/retry.py:44`
   - 확인된 사실: __and__ 메서드에서는 self가 retry_all인지 확인하여 평탄화를 수행하지만, __rand__ 메서드에서는 other가 retry_all인지 확인하여 평탄화를 수행하도록 구현되어 있습니다.

2. __or__에서는 self의 타입을 확인하여 평탄화하는 반면 __ror__에서는 other의 타입을 확인하여 평탄화하도록 다르게 구현된 이유가 무엇인가요?
   - 근거: `tenacity/retry.py:56`, `tenacity/retry.py:58`
   - 확인된 사실: __or__ 메서드에서는 self가 retry_any 인스턴스인지 확인하여 self.retries를 평탄화하지만, __ror__ 메서드에서는 self가 아닌 other가 retry_any 인스턴스인지를 확인하여 평탄화를 수행하고 있어 두 연산자 간 평탄화 처리 대상 조건에 차이가 존재합니다.

3. tenacity/retry.py와 달리 tenacity/wait.py에서는 retry_state.outcome.failed 여부를 사전에 검사하지 않고 exception()을 바로 호출하도록 작성된 특별한 이유가 있으신가요?
   - 근거: `tenacity/wait.py:172`, `tenacity/retry.py:275`
   - 확인된 사실: tenacity/retry.py 275~276행에서는 retry_state.outcome.failed 여부를 확인하여 성공 시 즉시 반환하는 조건문이 존재하지만, tenacity/wait.py 172행에서는 outcome.failed 확인 과정 없이 retry_state.outcome.exception()을 바로 호출하고 있습니다.

4. BaseRetrying.__init__에는 name 파라미터가 정의되어 있지만 retry 함수 파라미터에는 name이 포함되어 있지 않은 이유가 무엇인가요?
   - 근거: `tenacity/__init__.py:250`, `tenacity/__init__.py:262`
   - 확인된 사실: BaseRetrying.__init__ 메서드에는 name 파라미터가 정의되어 있으나, 동일한 모듈의 retry 함수 파라미터 목록에는 name 파라미터가 포함되어 있지 않습니다.

## 4. High-change areas

최근 60일간 반복적으로 변경된 영역이다. 변경 횟수는 git 이력에서 센 수치다.

| 파일 | 60일 변경 | 마지막 변경 |
|---|---|---|
| `tenacity/__init__.py` | 9 | 2026-08-06 |
| `tenacity/asyncio/__init__.py` | 5 | 2026-08-06 |
| `tenacity/retry.py` | 4 | 2026-08-05 |
| `tenacity/wait.py` | 3 | 2026-08-06 |
| `tenacity/_utils.py` | 1 | 2026-08-05 |
| `tenacity/tornadoweb.py` | 1 | 2026-08-05 |

## 5. Test evidence gaps

직접 연결된 테스트 근거를 찾지 못했습니다. 테스트가 없다는 뜻은 아니다.

| 파일 | 전체 커밋 |
|---|---|
| `tenacity/before_sleep.py` | 18 |
| `tenacity/after.py` | 16 |
| `tenacity/before.py` | 14 |
| `doc/source/conf.py` | 12 |
| `tenacity/nap.py` | 6 |

## 6. Dead-code candidates

정적 호출 경로에서 사용 근거를 찾지 못했습니다. 삭제를 권하는 것이 아니라 확인이 필요한 후보다.

| 위치 | 이름 | 종류 | confidence |
|---|---|---|---|
| `tenacity/__init__.py:704` | `instance` | variable | 100% |
| `tenacity/__init__.py:704` | `owner` | variable | 100% |
| `tenacity/__init__.py:708` | `instance` | variable | 100% |
| `tenacity/__init__.py:708` | `owner` | variable | 100% |
| `tenacity/_utils.py:58` | `level` | variable | 100% |
| `doc/source/conf.py:20` | `master_doc` | variable | 60% |
| `doc/source/conf.py:21` | `project` | variable | 60% |
| `doc/source/conf.py:25` | `extensions` | variable | 60% |
| `tenacity/__init__.py:161` | `NAME` | variable | 60% |
| `tenacity/__init__.py:177` | `NAME` | variable | 60% |

그 외 3개 후보.

## 7. First week

1. `tenacity/stop.py` 의 변경 이력을 읽고, 연결된 테스트가 정말 없는지 확인한다 (최근 60일 최다 변경 + 테스트 근거 없음)
2. 이전 개발자에게 물어볼 것: __and__에서는 self를, __rand__에서는 other를 대상으로 retry_all 여부를 검사하도록 서로 다르게 작성된 이유가 무엇인가요?
3. `tenacity/__init__.py:704` 의 `instance` 이 실제로 쓰이지 않는지 확인한다 (정적 분석으로는 호출 근거를 찾지 못함)
