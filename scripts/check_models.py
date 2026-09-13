"""Gemini 연결 확인 및 호출 가능한 모델 목록.

429(할당량 소진)나 404(모델 단종)가 났을 때 무엇이 남아 있는지 확인하는 용도.
할당량은 키(프로젝트) 단위이고, 같은 키 안에서도 모델별로 따로 걸린다.
API 키 값은 절대 출력하지 않는다.

사용법:
    py -m scripts.check_models
"""

import sys

from scripts.run_validation import ENV_PATH, make_client


def main() -> int:
    client = make_client()
    print(f"키 로드됨 ({ENV_PATH}, 값은 출력하지 않음)\n")

    print("=== generateContent 가능한 모델 ===")
    for m in client.models.list():
        if "generateContent" in (getattr(m, "supported_actions", None) or []):
            print(" ", m.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
