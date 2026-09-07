@echo off
setlocal

rem ===========================================================================
rem  인스타그램 일별 게시물 모니터링 - 하루 한 번 실행
rem ===========================================================================
rem  하는 일
rem    1) 이 파일이 들어있는 폴더로 이동합니다 (어디서 실행해도 안전합니다)
rem    2) 파이썬을 찾습니다 (가상환경 -> python -> py 순서)
rem    3) python instagram_crawler.py Daily_crawl 을 실행합니다
rem    4) 계정별 엑셀이 Daily_crawl 폴더에 쌓입니다
rem
rem  이 파일은 '게시물'을 기록합니다. 팔로워 수는 건드리지 않습니다.
rem  (팔로워 수는 run_follower_tracker.bat 이 따로 담당합니다)
rem
rem  실행 기록은 파이썬이 직접 logs\daily_crawl_날짜.log 에 남깁니다.
rem  한 파일에 두 곳에서 동시에 쓰면 내용이 섞일 수 있어, 여기서는
rem  화면 출력을 로그 파일로 돌리지 않습니다.
rem
rem  옵션은 그대로 넘길 수 있습니다.
rem    예) run_daily_crawl.bat --date 2026-09-07
rem        run_daily_crawl.bat --force
rem ===========================================================================

rem %~dp0 는 '이 배치 파일이 들어있는 폴더' 입니다.
cd /d "%~dp0"

rem --- 1) 파이썬 찾기 --------------------------------------------------------
rem  계정 이름에 한글이나 공백이 들어간 경로에서도 문제가 없도록
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
rem  윈도우의 %DATE% 는 지역 설정마다 형식이 달라 파이썬에게 물어봅니다.
set "TODAY="
for /f "usebackq delims=" %%d in (`%PYCMD% -c "import datetime;print(datetime.date.today().isoformat())"`) do set "TODAY=%%d"
if not defined TODAY set "TODAY=unknown-date"

rem --- 3) 폴더 준비 ----------------------------------------------------------
if not exist "logs" mkdir "logs"
if not exist "Daily_crawl" mkdir "Daily_crawl"

rem 로그와 화면에 한글이 깨지지 않도록 파이썬 출력을 UTF-8 로 맞춥니다.
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo Instagram daily post monitor - running...
echo Log file: %~dp0logs\daily_crawl_%TODAY%.log
echo Output  : %~dp0Daily_crawl

rem --- 4) 실행 ---------------------------------------------------------------
%PYCMD% instagram_crawler.py Daily_crawl %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo [WARN] Finished with errors. Please open the log file above.
)

rem 파이썬의 종료 코드를 그대로 돌려줍니다 (작업 스케줄러가 성공/실패를 알 수 있게).
exit /b %EXITCODE%
