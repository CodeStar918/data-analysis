@echo off
rem One-click dev launcher (backend 8000 + frontend 5173)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"
if errorlevel 1 pause
