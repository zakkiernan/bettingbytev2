@echo off
cd /d "%~dp0"
mkdir "logs" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_scheduler.ps1"
