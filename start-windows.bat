@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
if errorlevel 1 (
  echo.
  echo 启动没有完成，请查看上面的提示和新打开的终端窗口。
  pause
)
