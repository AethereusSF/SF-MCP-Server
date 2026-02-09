#!/bin/bash
# Start Salesforce MCP Server in HTTP/SSE mode (for Claude Code via ngrok)
# This runs separately from the stdio version used by Claude Desktop

echo "Starting Salesforce MCP Server in HTTP/SSE mode..."
echo "This is for Claude Code access via ngrok"
echo ""

cd "$(dirname "$0")"

# Use venv Python directly - no activation needed, works on all Python versions
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

echo "Server will run on port 8000"
echo "Press Ctrl+C to stop the server"
echo ""

venv/bin/python -m app.main --http
