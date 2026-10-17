@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-windows.ps1"
if errorlevel 1 (
  echo.
  echo 安装没有完成，请根据上面的提示处理后重试。
  pause
)
