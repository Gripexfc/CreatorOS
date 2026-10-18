@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-openclaw-windows.ps1"
set "exit_code=%errorlevel%"

if not "%exit_code%"=="0" (
  echo.
  echo OpenClaw 安装失败，请查看上面的提示。
  pause
)

exit /b %exit_code%
