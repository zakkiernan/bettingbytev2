@echo off
cd /d "%~dp0"
mkdir "logs" 2>nul
start "BettingByte Scheduler" /min "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run_scheduler.py"
