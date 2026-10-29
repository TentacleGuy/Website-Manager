@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0Installieren.ps1" (
  echo Bitte zuerst die ZIP-Datei vollstaendig entpacken.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installieren.ps1"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
