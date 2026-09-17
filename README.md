# Re:Code

**AI가 만든 저장소를 넣으면, 다음 사람에게 넘길 인수인계서를 만들어주는 서비스**

> AI가 쓴 코드는 아무도 읽은 적이 없어서, 물어볼 사람조차 없습니다.

<!-- TODO(PHASE 16, 9/18~19): 대표 이미지 삽입 (16:9, 문제 서사 시각화) -->
<!-- TODO(PHASE 17, 9/19): 데모 GIF 또는 스크린샷 5장 배치 -->

원티드 AI Championship 2026 출품작 · 접수 9/18 · 제출 9/20

---

## Problem

AI가 코드를 쓰는 속도는 빨라졌지만, 그 코드를 이해하는 속도는 빨라지지 않았습니다.

퇴사 인수인계는 누군가는 알고 있었던 것을 잃는 문제입니다. AI가 쓴 코드는 다릅니다. 세션이 끝나면 AI는 기억하지 못하고, 사람은 애초에 읽은 적이 없습니다. **처음부터 아무도 몰랐던 코드**가 쌓이고, 물어볼 대상 자체가 없습니다.

기존 정적 분석 도구의 규칙집은 사람이 코드를 쓴다는 전제로 설계됐습니다. AI 특유의 실패 유형은 그 규칙집에 없고, 기존 도구는 코드를 고치라고 말할 뿐 **사람에게 넘기는 것을 돕지 않습니다.**

## What Re:Code does

공개 GitHub URL 을 넣으면 다음 개발자가 손대기 전에 확인해야 할 **맥락과 질문**을 만들어줍니다.

**만들지 않는 것**:
- 코드 품질 점수 (Re:Code 는 코드 품질 검사기가 아닙니다)
- README/코드 요약 (Re:Code 는 요약 생성기가 아닙니다)
- "고쳐야 할 문제" 목록 (Re:Code 는 "확인해야 할 질문" 만 만듭니다)

**만드는 것 — 인수인계서 (`HANDOFF.md`)**:
1. 이 저장소가 하는 일 — 진입점과 핵심 흐름
2. 손대기 전에 알아야 할 것 — 위치, 왜 위험한지, 커밋 링크
3. 원저자에게 물어볼 질문
   > "재시도 횟수가 `payment.py` 는 3, `refund.py` 는 5인데 의도한 차이인가요?"
4. 첫 주에 할 일 3가지
   > "결제 재시도 로직에 테스트부터 붙이세요. 두 달간 일곱 번 고쳤는데 검증이 없습니다."

## Demo

**라이브 서비스**: <!-- TODO(PHASE 14, 9/17): 배포 URL 삽입 (Railway 또는 Render) -->

**데모 영상**: <!-- TODO(PHASE 16, 9/18~19): 2~3분 데모 영상 링크 -->

**자기참조 인수인계서** — Re:Code 를 Re:Code 로 분석한 결과:
[`evaluation/self_reference/HANDOFF.md`](evaluation/self_reference/HANDOFF.md)
(분석 시점 커밋 `ac8410c`, 모델 `gemini-3.5-flash-lite`, 후보 9쌍 전수 판정, 76초, $0)

**finding 5건 전부 실제 코드와 대조해 사실임을 확인했다. 억지 경고 0건.**
그중 2건은 우리가 모르고 있던 진짜 불일치였다:

1. **독스트링 정규식 범위 불일치** — `judge/embed.py` 는 `'''` 와 `"""` 를 모두 처리하는데
   `scripts/make_samples.py` 는 `"""` 만 처리한다. 뒤에 만든 것만 고치고 앞을 안 고친 드리프트
2. **테스트 파일 판별 규칙이 세 파일에서 서로 달랐다** — 필요할 때마다 따로 만들어
   뒤로 갈수록 규칙이 늘었다 (2026-09-17 `judge/languages.py` 로 통합해 해소)

나머지 3건 중 2건은 **의도한 설계**였다(레이어 분리, 화면 vs API 응답 차이). 질문 자체는
타당했고 답을 듣기 전에는 알 수 없는 종류였다 — 제품 정의("답을 정하지 않고 질문을 만든다")에 부합한다.

## Architecture

```
[웹 클라이언트]  URL 입력 / SSE 구독
      ▼
[API 서버 — FastAPI]  작업 등록, 진행 스트리밍
      ▼
   [작업 큐]
      ▼
[분석 워커 — Python]
   수집 → 정적 분석 → 절삭(2,000개) → 임베딩 후보 축소
        → LLM 판정 → 문서 생성(근거 링크 강제)
      ▼
[PostgreSQL] → 인수인계서 렌더링
```

## Analysis pipeline

1. **수집** — `git clone` + 커밋 히스토리 (GitHub API 없이 git CLI 만 사용)
2. **함수 추출** — Python 은 표준 `ast`, 나머지 언어는 `tree-sitter` 로 파싱
   (Java · C · C# · C++ · JavaScript · TypeScript · TSX). 함수 2,000개 상한
   (초과 시 커밋 빈도순 절삭). 언어 규칙은 `judge/languages.py` 한 곳에 모여 있다
3. **정적 분석** (LLM 없이 동작하는 근거)
   - High-Churn Hotspot — 60일간 커밋 밀집도. git 이력 기반이라 언어를 가리지 않는다
   - Dead-Code Candidate — Python 은 `vulture`. 나머지 언어는 **스코프 기반**으로 본다.
     `private` 메서드 · `static` 함수 · export 하지 않은 함수는 그 파일 밖에서 부를 수 없으므로,
     자기 파일 안에서 이름이 정의 자리 한 번만 나오면 호출되는 자리가 없다는 뜻이다.
     공개 API 는 저장소 밖에서 불릴 수 있어 처음부터 대상에 넣지 않는다.
     파싱이 깨진 파일로는 단정하지 않고 건너뛴다
   - Test Evidence Gap — Python 은 `import` 역추적. 나머지 언어는 이름 규칙
     (`FooTest.java` → `Foo.java`, `foo.spec.ts` → `foo.ts`)과 테스트가 대상 이름을
     실제로 부르는지로 연결한다
4. **후보 축소** — `sentence-transformers` (`all-MiniLM-L6-v2`) 로컬 임베딩. threshold 0.80. `numpy` 내적으로 cosine 유사도
5. **LLM 판정** — Google Gemini API 로 유사 쌍을 "의도적 분리인가, 맥락 상실로 인한 중복인가" 판정.
   모델 하나가 하루 한도를 다 쓰면 다음 모델로 자동 전환한다. 쌍은 항상 같은 언어끼리만 만들어진다
6. **문서 생성** — 근거 파일 경로·줄 번호·커밋 링크 강제. 근거 없는 finding 은 만들지 않음

**설계 결정**:
- 정적 분석은 결정론적이라 숫자가 틀리지 않음. LLM 은 규칙으로 불가능한 판정만 맡음
- LLM 이 흔들려도 정적 분석 결과는 남으므로 서비스가 통째로 무너지지 않음
- 전수 비교 금지 (django 5억 3천만 쌍). 임베딩으로 상위 후보만 추려 LLM 에 넘김
- 함수 2,000개 상한 (실측: django 32,679함수 → 2,000개, 피크 메모리 36MB)

## AI usage

**LLM (Google Gemini, `gemini-3-flash-preview`)**:
- 유사 함수 쌍 판정 — "의도적 분리인가, 맥락 상실인가"
- 에러 처리 방식 일관성 판정
- 무료 티어, 비용 $0

**로컬 임베딩 (`sentence-transformers`, `all-MiniLM-L6-v2`)**:
- 함수 유사도 계산
- 로컬 실행이라 API 호출·과금 없음

**품질 규칙 (강제)**:
- 모든 finding 에 근거 파일 경로 · 커밋 링크 포함
- 근거를 달 수 없으면 finding 을 만들지 않음
- 결과 0건 섹션은 표시하지 않음 ("경고 개수 부풀리기 금지")
- "AI 가 생성해서 생긴 문제" 같은 표현 금지 (원저자 의도 단정 금지)

**개발 과정에서 쓴 AI 도구**:
- **Claude Code** (Anthropic CLI) · **Codex** (OpenAI CLI)
- 2인 팀이 각자 한 도구씩 쓰며 순차 릴레이 방식으로 개발
- 개발 과정 자체가 "AI 가 만든 저장소" 의 실례

## Evaluation

**PHASE 9 내부 검증** (2026-09-15, n=31):

| 저장소 | 함수 | 후보 | 판정 | finding | useful | 유용률 |
|---|---|---|---|---|---|---|
| psf/cachecontrol | 232 | 9 | 9 (전수) | 3 | 3 | 100% |
| openvax/mhctools | 1,814 | 100 | 11 (표본) | 7 | 5 | 71% |
| django/django | 2,000 (상한) | 100 | 20 (표본) | 10 | 7 | 70% |
| psf/requests | 711 | 35 | 20 (표본) | 11 | 6 | 55% |

**전체 유용률: 68% (21/31), AI 소스 검증 baseline** — 자기평가 편향 회피를 위해 정확도 과장 없이 "내부 검증(n=31)" 으로 표기.

**PHASE 13 사용자 테스트** (2026-09-17): **팀 내부 2명 × A/B 교차 = 세션 4회.**
저장소는 `jd/tenacity` 와 `pyeve/cerberus` 로 규모를 맞췄고(18파일 / 함수 167 vs 195),
각자 A·B 를 한 번씩 서로 반대 저장소로 수행했다.

| 항목 | A 조건 (리포트 없음) | B 조건 (리포트 있음) |
|---|---|---|
| 확인 지점을 찾기까지 (평균) | 7분 | **3분** |
| 물어볼 질문 수 (합) | 4개 | **6개** |
| 사용 의향 (평균, 1~5) | 1.0 | **5.0** |

**질문 유용률 6/9 (67%)** — tenacity 2/4, cerberus 4/5. 오탐 지적 3건은 "굳이 질문하지
않아도 알 수 있는 내용" 이었다.

PHASE 9 의 AI baseline(68%)과 사람 평가(67%)가 거의 일치했다. 서로 독립적인 방법이다.

**한계를 먼저 밝힌다**: 표본 2명 · 세션 4회로 25절 요구(3~5명)에 미달하고, 두 사람 모두
도구 제작자 본인이라 **자기평가 편향**이 있다. 또한 대상 저장소는 영어, 리포트는 한글이라
**A/B 격차에 언어 장벽이 섞여 있어 실제 도구 효과보다 부풀려져 있을 수 있다.**
통계적 유의성은 주장하지 않는다. 원자료: [`evaluation/user_test/응답시트.md`](evaluation/user_test/응답시트.md)

**대형 저장소 안정성**: django (2,000함수 상한, 후보 100쌍) 에서 **오류 0건** 완주. 21절 목표 "대형 repo 실패 여부" 확보.

**비용**: Gemini 무료 티어 사용, $0.

## Data handling

**Re:Code 는 저장소 전체를 외부 모델에 보내지 않는다.**

함수 추출과 유사도 계산은 전부 로컬에서 끝난다. 임베딩은 `sentence-transformers` 의
`all-MiniLM-L6-v2`(87MB)를 내려받아 CPU 로 직접 돌리므로 네트워크를 쓰지 않는다.
외부로 나가는 것은 그렇게 좁혀진 후보 쌍뿐이다.

| 저장소 | 분석 대상 | 외부 모델로 보낸 코드 |
|---|---|---|
| google/gson | 57,382줄 | 15쌍 · 338줄 (**0.59%**) |
| serilog/serilog | 24,982줄 | 10쌍 · 100줄 (**0.40%**) |
| DaveGamble/cJSON | 22,805줄 | 8쌍 · 165줄 (**0.72%**) |
| axios/axios | 41,740줄 | 15쌍 · 686줄 (**1.64%**) |

gson 기준으로 유사도 비교 190,653번이 전부 로컬에서 일어났고, 그중 15쌍만 외부로 나갔다.
이 수치는 분석할 때마다 실제로 재서 리포트 화면과 `HANDOFF.md` 에 함께 적는다.

네트워크를 호출하는 코드는 `judge/llm.py` 한 파일뿐이다. `analyzer/`(정적 근거),
`judge/extract.py`(함수 추출), `judge/embed.py`(유사도)에는 네트워크 호출이 없다.

**사내 도입 시 권고**: 현재 판정 모델은 Gemini 무료 등급을 쓴다. 코드가 회사 밖으로
나가면 안 되는 환경에서는 `judge/llm.py` 의 판정 모델을 사내 LLM 으로 교체하면 된다.
나머지 파이프라인은 이미 로컬에서 돌고 있어 바꿀 것이 없다.
(현재 코드는 Gemini SDK 를 직접 호출한다. 교체 지점이 한 파일로 모여 있을 뿐,
로컬 LLM 연동 자체는 아직 구현하지 않았다.)

## Limitations

- **Python, Java, C, C#, C++, JavaScript, TypeScript 지원** (2026-09-17). HTML 은 함수가 없어 언어 구성 집계와 High-Churn 에만 포함한다
- **C/C++ 은 매크로가 많으면 파싱이 깨진다** (실측: cJSON 62%, spdlog 18% 만 깨끗하게 읽힘). 깨진 파일로는 '사용 근거 없음' 을 단정하지 않고 건너뛴다
- **JavaScript/TypeScript 는 이름 있는 함수만 비교한다.** `arr.map(x => x * 2)` 같은 익명 콜백은 가리킬 이름이 없어 질문을 만들 수 없다 (실측 이름 해석률 JS 31.5%, TS 41.5%. Java/C# 은 100%)
- **함수 2,000개 상한** — 대형 저장소는 커밋 빈도 상위 파일만 분석 (실측: django 2,616 파일 중 15개 파일로 축약)
- **private 저장소 미지원** — 인증 비용, 개인정보 우려
- **LLM 판정 안정성** — 모델 선택이 정밀도에 직접 영향 (STATUS.md 실측 기록). 오탐 유형 3가지 확인:
  1. 컨텍스트 부재 (함수 두 개만 잘라 던져 주변 정규화 로직 못 봄)
  2. 스타일 필터 누락 (f-string vs %, 명시적 기본값 전달)
  3. 클래스 성격 판정 부재 (근본 성격이 다른 클래스 비교)
- **facade 패턴 test_map false negative** — `__init__.py` 에서 re-export 하는 구조에서 원 파일-테스트 연결 놓침. "직접 연결된 근거를 찾지 못했다" 표현으로 안전 처리

## Run locally

**요구사항**:
- Python 3.12
- Docker (PostgreSQL 16 컨테이너용)
- Gemini API 키 ([Google AI Studio](https://aistudio.google.com) 에서 무료 발급)

**설치**:
```bash
git clone https://github.com/<owner>/recode.git
cd recode
py -3.12 -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**환경 변수** (`.env`):
```
GITHUB_TOKEN=<optional, PAT>
GEMINI_API_KEY=<required>
DATABASE_URL=postgresql://user:pass@localhost:5432/recode
```

**PostgreSQL 컨테이너**:
```bash
docker run -d --name recode-db -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:16
```

**CLI 로 분석**:
```bash
py analyze.py https://github.com/psf/requests
# 결과: outputs/psf__requests/HANDOFF.md
```

**옵션**:
- `--skip-llm` — LLM 없이 정적 근거만으로 리포트 (quota 부담 0)
- `--limit=N` — 후보 N개만 판정
- `--model=이름` — 첫 모델 지정. 하루 한도(모델당 20회)를 다 쓰면 다음 모델로
  자동 전환한다(`judge/llm.FALLBACK_MODELS`). 전부 소진되면 남은 후보를 건너뛰고
  그때까지의 결과로 보고서를 만든다. 소진된 모델을 건너뛰려면 살아 있는 모델을 직접 지정할 것

**웹 서버**:
```bash
py -m uvicorn app.main:app --port 8000
# http://localhost:8000
```

> ⚠ **`--reload` 를 붙이지 말 것.** watchfiles 가 프로젝트 트리 전체에서 `*.py` 변경을
> 감시하는데, `git clone` 이 `repos/` 에 `.py` 를 쏟아내면 이를 소스 변경으로 보고
> 서버를 재시작한다. 그때 백그라운드의 `git` 이 콘솔 CTRL_C 를 받고 죽어서
> **처음 보는 저장소 분석이 100% 실패한다.**
> 개발 중 자동 리로드가 필요하면 감시 범위를 좁힌다:
> `--reload --reload-dir app --reload-dir judge --reload-dir analyzer`

DB 는 `docker-compose.yml` 의 `postgres:16` 을 쓴다. 먼저 `docker compose up -d` 로 띄울 것.

## Team

<!-- TODO(PHASE 17, 9/19): 팀원 이름 및 역할 -->
- **A**: <역할>
- **B**: <역할>

**릴레이 개발 방식**: 두 개발자가 Claude Code / Codex 를 각각 사용하여 순차 릴레이 (`git pull` → 작업 → `git push`). 폴더 소유권 없이 세션 열린 쪽에서 다음 phase 를 이어감.

---

## 참고 문서

- [개발계획서](docs/ReCode_개발계획서.md) — 프로젝트 정의, 아키텍처, 심사 폼 답변 <!-- TODO: iCloud 문서 경로 정리 방식 결정 -->
- [세부 실행 계획](docs/ReCode_개발환경_및_세부실행계획.md) — PHASE 0~17 상세 <!-- TODO: 위와 동일 -->
- [STATUS.md](STATUS.md) — 오늘까지의 진행 상황과 다음 작업

## License

<!-- TODO(PHASE 17, 9/19): 라이선스 결정 (MIT 등) -->

## 최종 핵심 문장

> **Re:Code 는 코드를 설명하는 도구가 아니라, 다음 개발자가 무엇을 물어봐야 하는지 찾아주는 도구다.**
>
> **Every finding needs evidence. If there is no evidence, do not generate it.**
