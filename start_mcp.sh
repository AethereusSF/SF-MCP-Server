#!/bin/bash
cd "$(dirname "$0")"

# Use venv Python directly - no activation needed, works on all Python versions
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

venv/bin/python -m app.main --mcp-stdio
