@echo off
setlocal

rem ===========================================================================
rem  구글 시트 업로드 자동 실행 등록 - 이 파일을 한 번만 실행하면 됩니다
rem ===========================================================================
rem  등록되는 작업
rem    InstagramSheetsUpload-Weekday : 영업일(월~금) 오전 10:00 실행
rem
rem  주말에는 돌지 않습니다. 다만 윈도우 작업 스케줄러는 한국 공휴일을
rem  알지 못하므로 공휴일에도 실행됩니다. 그날은 전날 자료가 그대로 올라갈
rem  뿐이라 문제가 되지 않습니다.
rem
rem  수집 일정과 이어지도록 10시로 잡았습니다.
rem    09:00 팔로워 수집 -> 09:30 게시물 수집 -> 10:00 시트 업로드
rem
rem  여러 번 실행해도 시트가 망가지지 않습니다. replace 방식은 지정한 범위를
rem  매번 다시 쓰기 때문에, 같은 날 두 번 돌려도 결과가 같습니다.
rem
rem  이 파일은 CP949 로 저장되어 있고 chcp 를 쓰지 않습니다.
rem  chcp 65001 상태에서는 cmd 가 한글 주석 줄을 잘못 읽는 경우가 있습니다.
rem
rem  경로는 %~dp0 를 쓰므로 폴더를 옮기면 이 파일만 다시 실행하면 됩니다.
rem ===========================================================================

cd /d "%~dp0"
set "BATFILE=%~dp0run_sheets_upload.bat"
set "TASKNAME=InstagramSheetsUpload-Weekday"

if not exist "%BATFILE%" (
    echo [ERROR] run_sheets_upload.bat not found in this folder.
    pause >nul
    exit /b 1
)

echo ==================================================
echo  Registering Google Sheets upload task
echo  Target: %BATFILE%
echo  Schedule: Mon-Fri 10:00
echo ==================================================
echo.

schtasks /Create /TN "%TASKNAME%" /TR "\"%BATFILE%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 10:00 /F
if errorlevel 1 goto :failed
echo   [OK] Weekday 10:00 task registered.
echo.

echo ==================================================
echo  Applying battery / missed-run settings
echo ==================================================
rem  StartWhenAvailable : 10시에 PC 가 꺼져 있었다면 켜진 뒤 바로 한 번 실행
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=Get-ScheduledTask -TaskName '%TASKNAME%'; $t.Settings.StartWhenAvailable=$true; $t.Settings.DisallowStartIfOnBatteries=$false; $t.Settings.StopIfGoingOnBatteries=$false; $t.Settings.ExecutionTimeLimit='PT30M'; Set-ScheduledTask -InputObject $t | Out-Null; Write-Host ('  [OK] ' + '%TASKNAME%')"
if errorlevel 1 echo   [WARN] Could not apply extra settings. Task still works, but may skip runs on battery.
echo.

echo ==================================================
echo  Checking configuration (dry run)
echo ==================================================
rem  실제로 올리지 않고 설정이 맞는지만 확인합니다.
call "%BATFILE%" --dry-run
echo.

echo Log file: %~dp0logs\
echo.
echo Current state:
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ScheduledTask -TaskName '%TASKNAME%' | Select-Object TaskName,State,@{n='Battery OK';e={-not $_.Settings.DisallowStartIfOnBatteries}},@{n='Catch up';e={$_.Settings.StartWhenAvailable}} | Format-Table -AutoSize"
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
