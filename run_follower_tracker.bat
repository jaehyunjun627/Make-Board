@echo off
setlocal

rem ===========================================================================
rem  인스타그램 경쟁사 팔로워 추적기 - 윈도우 실행 파일
rem ===========================================================================
rem  하는 일
rem    1) 이 파일이 들어있는 폴더로 이동합니다 (어디서 실행해도 동작합니다)
rem    2) 파이썬을 찾습니다 (가상환경 -> python -> py 런처 순서)
rem    3) python instagram_crawler.py track-followers 를 실행합니다
rem    4) 실행 내용을 logs\tracker_날짜.log 파일에 남깁니다
rem
rem  이 파일은 '팔로워 수'만 기록합니다. 게시물은 수집하지 않습니다.
rem  (매일 자동으로 돌려도 result_*.xlsx 같은 결과 파일이 쌓이지 않습니다)
rem
rem  옵션을 그대로 넘길 수 있습니다.  예) run_follower_tracker.bat --force
rem ===========================================================================

rem %~dp0 는 '이 배치 파일이 들어있는 폴더' 입니다.
rem 작업 폴더가 어디로 잡히든 항상 프로젝트 폴더에서 실행되게 만듭니다.
cd /d "%~dp0"

rem --- 1) 파이썬 찾기 --------------------------------------------------------
rem  개인 윈도우 사용자 이름(C:\Users\...)을 파일에 적지 않기 위해
rem  항상 이 폴더 기준의 상대 경로로만 찾습니다.
set "PYCMD="
if exist ".venv\Scripts\python.exe" set "PYCMD=".venv\Scripts\python.exe""
if not defined PYCMD if exist "venv\Scripts\python.exe" set "PYCMD="venv\Scripts\python.exe""
if not defined PYCMD if exist "env\Scripts\python.exe" set "PYCMD="env\Scripts\python.exe""

if not defined PYCMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
)

if not defined PYCMD (
    where py >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)

if not defined PYCMD (
    echo [ERROR] Python not found.
    echo         Install Python 3.9 or newer, and check "Add Python to PATH".
    exit /b 1
)

rem --- 2) 오늘 날짜 구하기 ---------------------------------------------------
rem  윈도우의 %DATE% 는 지역 설정마다 형식이 달라서 파일 이름에 쓰기 위험합니다.
rem  그래서 파이썬으로 YYYY-MM-DD 를 직접 만들어 씁니다.
set "TODAY="
for /f "usebackq delims=" %%d in (`%PYCMD% -c "import datetime;print(datetime.date.today().isoformat())"`) do set "TODAY=%%d"
if not defined TODAY set "TODAY=unknown-date"

rem --- 3) 로그 폴더 준비 -----------------------------------------------------
if not exist "logs" mkdir "logs"
set "LOGFILE=logs\tracker_%TODAY%.log"

rem 로그 파일의 한글이 깨지지 않도록 파이썬 출력만 UTF-8 로 고정합니다.
rem (이 배치 파일 자체는 CP949 로 저장돼 있습니다. chcp 65001 을 쓰면
rem  cmd 가 한글 주석 줄을 파싱하다 중간에서 끊는 알려진 문제가 있습니다.)
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo Instagram follower tracker - running...
echo Log file: %~dp0%LOGFILE%

rem --- 4) 실행 ---------------------------------------------------------------
rem  화면 출력과 오류 메시지를 모두 로그 파일 뒤에 덧붙입니다(2>&1).
>> "%LOGFILE%" echo.
>> "%LOGFILE%" echo ==================================================
>> "%LOGFILE%" echo [START] %TODAY% %TIME%

%PYCMD% instagram_crawler.py track-followers %* >> "%LOGFILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"

>> "%LOGFILE%" echo [END]   %TODAY% %TIME%  (exit code %EXITCODE%)

if not "%EXITCODE%"=="0" echo [WARN] Finished with errors. Please open the log file above.
exit /b %EXITCODE%
