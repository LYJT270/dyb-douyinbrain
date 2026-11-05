@echo off
chcp 65001 >nul
title Douyin-brain Setup
echo Douyin-brain - preparing your local Agent skill
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set "dyb_exit=%errorlevel%"
echo.
if not "%dyb_exit%"=="0" echo Setup needs attention. Give the output above to your Agent.
pause
exit /b %dyb_exit%
