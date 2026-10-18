@echo off
setlocal
cd /d "%~dp0"

echo CreatorOS Windows 一键启动
echo 项目目录：%~dp0
echo.

call "%~dp0start-windows.bat"
set "exit_code=%errorlevel%"

if not "%exit_code%"=="0" (
  echo.
  echo 启动失败，保持窗口以便查看错误信息。
  pause
)

exit /b %exit_code%
