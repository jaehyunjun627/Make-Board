@echo off
setlocal

rem ===========================================================================
rem  구글 시트 업로드 - 하루 한 번 실행
rem ===========================================================================
rem  하는 일
rem    1) 이 파일이 들어있는 폴더로 이동합니다
rem    2) 파이썬을 찾습니다 (가상환경 -> python -> py 순서)
rem    3) python sheets_uploader.py 를 실행합니다
rem    4) 수집 결과를 구글 시트에 기록합니다
rem
rem  브라우저가 켜져 있을 필요가 없습니다. 공식 API 로 직접 기록합니다.
rem
rem  옵션은 그대로 넘길 수 있습니다.
rem    예) run_sheets_upload.bat --dry-run
rem ===========================================================================

cd /d "%~dp0"

rem --- 1) 파이썬 찾기 --------------------------------------------------------
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
set "TODAY="
for /f "usebackq delims=" %%d in (`%PYCMD% -c "import datetime;print(datetime.date.today().isoformat())"`) do set "TODAY=%%d"
if not defined TODAY set "TODAY=unknown-date"

rem --- 3) 폴더 준비 ----------------------------------------------------------
if not exist "logs" mkdir "logs"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo Google Sheets upload - running...
echo Log file: %~dp0logs\sheets_upload_%TODAY%.log

rem --- 4) 실행 ---------------------------------------------------------------
%PYCMD% sheets_uploader.py %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo [WARN] Finished with errors. Please open the log file above.
)

exit /b %EXITCODE%
