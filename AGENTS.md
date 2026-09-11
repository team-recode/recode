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

## 현재 제약 (2026-09-13 이후)

- `judge/` 폴더는 ①② 사전 검증(9/13 오전) 결과가 나오기 전까지 손대지 않는다.
- 그 전까지 작업은 `analyzer/`(③④⑥)와 세팅 · 문서 위주.
- 저장소 락 커밋(9/12)에는 `anthropic`, `openai`가 남아 있다. **`judge/` 코딩 시작 전 반드시 교체**:
  ```powershell
  pip uninstall anthropic openai -y
  pip install google-genai sentence-transformers
  pip freeze > requirements.txt
  git add requirements.txt
  git commit -m "chore: anthropic/openai 제거, google-genai/sentence-transformers 추가"
  ```

## 참고 문서

- `ReCode_개발환경_및_세부실행계획.md` — 세팅 규약(1~8절), PHASE 0~17 세부 실행(9~36절)
- `ReCode_개발계획서.md` — 프로젝트 정의, 아키텍처, 심사 폼 답변 초안
- `STATUS.md` — 오늘까지의 진행 상황과 다음 첫 순서

## 최종 핵심 문장

방향이 흔들리면 아래로 돌아온다.

> **Re:Code는 코드를 설명하는 도구가 아니라, 다음 개발자가 무엇을 물어봐야 하는지 찾아주는 도구다.**
>
> **Every finding needs evidence. If there is no evidence, do not generate it.**
