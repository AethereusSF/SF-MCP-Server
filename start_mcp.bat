@echo off
cd /d "%~dp0"

REM Use venv Python directly - no activation needed, works on all Python versions
if not exist venv\Scripts\python.exe (
    echo ERROR: Virtual environment not found. Please run setup.bat first.
    exit /b 1
)

venv\Scripts\python.exe -m app.main --mcp-stdio
