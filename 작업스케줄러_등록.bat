@echo off
setlocal

rem ===========================================================================
rem  작업 스케줄러 등록 - 이 파일은 한 번만 실행하면 됩니다
rem ===========================================================================
rem  등록되는 작업 2개
rem    InstagramFollowerTracker-Logon : 로그인하고 2분 뒤 실행
rem    InstagramFollowerTracker-Daily : 매일 오전 9시 실행
rem
rem  둘 다 등록해도 안전합니다. 중복 방지 기능이 있어서 계정마다 하루 한 번만
rem  기록되고, 그날 두 번째 실행부터는 건너뛰고 몇 초 만에 끝납니다.
rem
rem  등록 뒤에 아래 3가지 설정을 추가로 켭니다. schtasks 명령으로는 못 켜는
rem  항목이라 파워셸로 손봅니다. 노트북에서는 이게 없으면 실행이 자주 빠집니다.
rem    - 놓친 작업은 켜자마자 실행  (9시에 PC 가 꺼져 있었던 날을 보충)
rem    - 배터리로 켜도 실행         (기본값은 전원 안 꽂으면 아예 안 돕니다)
rem    - 실행 중 배터리로 바뀌어도 계속
rem
rem  이 파일은 CP949 로 저장돼 있고 chcp 를 쓰지 않습니다.
rem  chcp 65001 상태에서는 cmd 가 한글 주석 줄을 파싱하다 중간에서 끊습니다.
rem
rem  경로는 %~dp0 로 계산하므로 폴더를 옮기면 이 파일만 다시 실행하면 됩니다.
rem ===========================================================================

cd /d "%~dp0"
set "BATFILE=%~dp0run_follower_tracker.bat"
set "TASK1=InstagramFollowerTracker-Logon"
set "TASK2=InstagramFollowerTracker-Daily"

if not exist "%BATFILE%" (
    echo [ERROR] run_follower_tracker.bat not found in this folder.
    pause >nul
    exit /b 1
)

echo ==================================================
echo  Registering Windows scheduled tasks
echo  Target: %BATFILE%
echo ==================================================
echo.

schtasks /Create /TN "%TASK1%" /TR "\"%BATFILE%\"" /SC ONLOGON /DELAY 0002:00 /F
if errorlevel 1 goto :failed
echo   [OK] Logon task registered.
echo.

schtasks /Create /TN "%TASK2%" /TR "\"%BATFILE%\"" /SC DAILY /ST 09:00 /F
if errorlevel 1 goto :failed
echo   [OK] Daily 09:00 task registered.
echo.

echo ==================================================
echo  Applying battery / missed-run settings
echo ==================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($n in '%TASK1%','%TASK2%'){$t=Get-ScheduledTask -TaskName $n; $t.Settings.StartWhenAvailable=$true; $t.Settings.DisallowStartIfOnBatteries=$false; $t.Settings.StopIfGoingOnBatteries=$false; $t.Settings.ExecutionTimeLimit='PT1H'; Set-ScheduledTask -InputObject $t | Out-Null; Write-Host ('  [OK] ' + $n)}"
if errorlevel 1 echo   [WARN] Could not apply extra settings. Tasks still work, but may skip runs on battery.
echo.

echo ==================================================
echo  Running once now to check
echo ==================================================
schtasks /Run /TN "%TASK2%"
echo.
echo Started. Log file: %~dp0logs\
echo If today is already recorded, every account will just be skipped. That is correct.
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
