@echo off
setlocal

rem ===========================================================================
rem  데일리 크롤러 자동 실행 등록 - 이 파일은 한 번만 실행하면 됩니다
rem ===========================================================================
rem  등록되는 작업 2개
rem    InstagramDailyCrawl-Logon : 로그인하고 5분 뒤 실행
rem    InstagramDailyCrawl-Daily : 매일 오전 09:30 실행
rem
rem  팔로워 추적기(09:00)와 30분 간격을 둔 이유는 둘 다 브라우저를 띄우기
rem  때문입니다. 겹쳐 돌면 서로 느려지거나 로그인 세션이 꼬일 수 있습니다.
rem
rem  두 개를 다 등록해도 게시물이 중복으로 쌓이지 않습니다. Daily_crawl 은
rem  같은 게시물을 링크로 알아보고, 이미 채워진 날짜 칸은 그대로 두기
rem  때문에 하루에 몇 번을 돌려도 결과가 같습니다.
rem
rem  이 파일은 CP949 로 저장되어 있고 chcp 를 쓰지 않습니다.
rem  chcp 65001 상태에서는 cmd 가 한글 주석 줄을 파싱하다 중간에서 끊습니다.
rem
rem  경로는 %~dp0 로 계산하므로 폴더를 옮기면 이 파일만 다시 실행하면 됩니다.
rem ===========================================================================

cd /d "%~dp0"
set "BATFILE=%~dp0run_daily_crawl.bat"
set "TASK1=InstagramDailyCrawl-Logon"
set "TASK2=InstagramDailyCrawl-Daily"

if not exist "%BATFILE%" (
    echo [ERROR] run_daily_crawl.bat not found in this folder.
    pause >nul
    exit /b 1
)

echo ==================================================
echo  Registering Daily_crawl scheduled tasks
echo  Target: %BATFILE%
echo ==================================================
echo.

schtasks /Create /TN "%TASK1%" /TR "\"%BATFILE%\"" /SC ONLOGON /DELAY 0005:00 /F
if errorlevel 1 goto :failed
echo   [OK] Logon task registered.
echo.

schtasks /Create /TN "%TASK2%" /TR "\"%BATFILE%\"" /SC DAILY /ST 09:30 /F
if errorlevel 1 goto :failed
echo   [OK] Daily 09:30 task registered.
echo.

echo ==================================================
echo  Applying battery / missed-run settings
echo ==================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($n in '%TASK1%','%TASK2%'){$t=Get-ScheduledTask -TaskName $n; $t.Settings.StartWhenAvailable=$true; $t.Settings.DisallowStartIfOnBatteries=$false; $t.Settings.StopIfGoingOnBatteries=$false; $t.Settings.ExecutionTimeLimit='PT2H'; Set-ScheduledTask -InputObject $t | Out-Null; Write-Host ('  [OK] ' + $n)}"
if errorlevel 1 echo   [WARN] Could not apply extra settings. Tasks still work, but may skip runs on battery.
echo.

echo ==================================================
echo  Running once now to check
echo ==================================================
schtasks /Run /TN "%TASK2%"
echo.
echo Started. Log file: %~dp0logs\
echo Result folder: %~dp0Daily_crawl\
echo Running twice in one day does not create duplicate rows. That is by design.
echo.
echo Current state:
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ScheduledTask -TaskName '%TASK1%','%TASK2%' | Select-Object TaskName,State,@{n='Battery OK';e={-not $_.Settings.DisallowStartIfOnBatteries}},@{n='Catch up';e={$_.Settings.StartWhenAvailable}} | Format-Table -AutoSize"
echo.
echo Done. Press any key to close this window.
pause >nul
exit /b 0

:failed
echo.
echo [ERROR] Registration failed.
echo   Try: right-click this file, then "Run as administrator"
echo.
pause >nul
exit /b 1
