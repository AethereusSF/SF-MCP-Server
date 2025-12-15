@echo off
REM Start Salesforce MCP Server in HTTP/SSE mode (for Claude Code via ngrok)
REM This runs separately from the stdio version used by Claude Desktop

echo Starting Salesforce MCP Server in HTTP/SSE mode...
echo This is for Claude Code access via ngrok
echo.

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo Server will run on port 8000
echo Press Ctrl+C to stop the server
echo.

py -m app.main --http
