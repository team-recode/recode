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
<!-- TODO(PHASE 12, 9/17): 자기참조 HANDOFF.md 링크 -->

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
2. **함수 추출** — `ast` 로 함수 파싱. 함수 2,000개 상한 (초과 시 커밋 빈도순 절삭)
3. **정적 분석** (LLM 없이 동작하는 근거)
   - High-Churn Hotspot — 60일간 커밋 밀집도
   - Dead-Code Candidate — `vulture` 로 미사용 코드 탐지
   - Test Evidence Gap — `import` 역추적으로 테스트-코드 연결 확인
4. **후보 축소** — `sentence-transformers` (`all-MiniLM-L6-v2`) 로컬 임베딩. threshold 0.80. `numpy` 내적으로 cosine 유사도
5. **LLM 판정** — Google Gemini API (`gemini-3-flash-preview`) 로 유사 쌍을 "의도적 분리인가, 맥락 상실로 인한 중복인가" 판정
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

**PHASE 13 개발자 3~5명 외부 검증** (9/17~18): <!-- TODO(PHASE 13, 9/17~18): 외부 검증 결과 반영 -->

**대형 저장소 안정성**: django (2,000함수 상한, 후보 100쌍) 에서 **오류 0건** 완주. 21절 목표 "대형 repo 실패 여부" 확보.

**비용**: Gemini 무료 티어 사용, $0.

## Limitations

- **파이썬 저장소만 전체 분석 지원**. 다른 언어는 커밋 히스토리 기반 부분 리포트 (High-Churn, Test Evidence Gap 만)
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
- `--model=이름` — Gemini 모델 지정 (`gemini-3-flash-preview` 권장)

**웹 서버**: <!-- TODO(PHASE 10, 9/16): FastAPI 실행 명령 -->

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
