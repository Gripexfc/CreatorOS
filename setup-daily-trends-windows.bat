@echo off
setlocal
cd /d "%~dp0"

set "task_time=%~1"
if "%task_time%"=="" set "task_time=08:00"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register-daily-trends-windows.ps1" -Time "%task_time%"
set "exit_code=%errorlevel%"

if not "%exit_code%"=="0" (
  echo.
  echo 每日热点任务注册失败，请查看上面的错误信息。
  pause
)

exit /b %exit_code%
