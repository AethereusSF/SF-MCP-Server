@echo off
REM Start Salesforce MCP Server in HTTP/SSE mode (for Claude Code via ngrok)
REM This runs separately from the stdio version used by Claude Desktop

echo Starting Salesforce MCP Server in HTTP/SSE mode...
echo This is for Claude Code access via ngrok
echo.

cd /d "%~dp0"

REM Use venv Python directly - no activation needed, works on all Python versions
if not exist venv\Scripts\python.exe (
    echo ERROR: Virtual environment not found. Please run setup.bat first.
    exit /b 1
)

echo Server will run on port 8000
echo Press Ctrl+C to stop the server
echo.

venv\Scripts\python.exe -m app.main --http
