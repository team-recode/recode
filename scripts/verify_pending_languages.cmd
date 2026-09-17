@echo off
REM 아직 LLM 판정까지 못 돌린 언어(TSX, C++)를 하루 할당량이 초기화된 뒤에 마저 돌린다.
REM Gemini 무료 등급의 requests-per-day 는 태평양 시간 자정(한국 시간 16:00)에 초기화된다.
REM Claude Code 를 꺼놔도 PC 만 켜져 있으면 작업 스케줄러가 이 파일을 실행한다.
REM
REM 등록:
REM   schtasks /Create /TN "ReCode 언어검증" /SC ONCE /ST 16:05 /TR "<이 파일 경로>"
REM 해제:
REM   schtasks /Delete /TN "ReCode 언어검증" /F

cd /d "%~dp0.."

set PYTHONIOENCODING=utf-8
set LOG=%~dp0..\outputs\verify_pending_languages.log

echo ===== %DATE% %TIME% 시작 ===== >> "%LOG%"

REM TSX. zustand 는 .tsx 파일 13개에서 함수 369개가 나온다.
echo [1/2] pmndrs/zustand (TSX) >> "%LOG%"
".venv\Scripts\python.exe" analyze.py https://github.com/pmndrs/zustand --limit=8 >> "%LOG%" 2>&1

REM C++. spdlog 는 헤더 전용 C++ 라 .h 도 C++ 로 읽힌다.
echo [2/2] gabime/spdlog (C++) >> "%LOG%"
".venv\Scripts\python.exe" analyze.py https://github.com/gabime/spdlog --limit=8 >> "%LOG%" 2>&1

echo ===== %DATE% %TIME% 끝 ===== >> "%LOG%"
