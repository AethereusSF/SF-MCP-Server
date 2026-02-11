#!/bin/bash
# ========================================
# Salesforce MCP Server Setup Script
# ========================================
# This script will:
# 1. Create a Python virtual environment
# 2. Install all required dependencies
# 3. Test the server installation
# ========================================

cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "Salesforce MCP Server Setup"
echo "========================================"
echo ""

# Check if Python is installed (try "python3" first, then "python")
echo "[1/4] Checking Python installation..."
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python 3.11 or higher from https://www.python.org"
    exit 1
fi

$PYTHON_CMD --version
echo "Python found!"
echo ""

# Create virtual environment
echo "[2/4] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully!"
fi
echo ""

# Install dependencies (using venv's Python directly - no activation needed)
echo "[3/4] Installing dependencies from requirements.txt..."
echo "Upgrading pip..."
venv/bin/python -m pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upgrade pip"
    exit 1
fi

echo "Installing requirements..."
venv/bin/python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi
echo "Dependencies installed successfully!"
echo ""

# Setup .env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    if cp .env.example .env 2>/dev/null; then
        echo ".env file created. Please configure it before running the server."
    else
        echo "WARNING: Could not create .env file. Please copy .env.example to .env manually."
    fi
    echo ""
fi

# Test the installation
echo "[4/4] Testing server installation..."
echo "Running dependency import tests..."

venv/bin/python -c "import mcp; print('  MCP library: OK')"
if [ $? -ne 0 ]; then
    echo "WARNING: MCP library test failed"
fi

venv/bin/python -c "import simple_salesforce; print('  Salesforce library: OK')"
if [ $? -ne 0 ]; then
    echo "WARNING: Salesforce library test failed"
fi

venv/bin/python -c "import cryptography; print('  Cryptography library: OK')"
if [ $? -ne 0 ]; then
    echo "WARNING: Cryptography library test failed"
fi

venv/bin/python -c "import pydantic; print('  Pydantic library: OK')"
if [ $? -ne 0 ]; then
    echo "WARNING: Pydantic library test failed"
fi
echo ""

echo "========================================"
echo "Setup completed successfully!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Get your license key from MCP Admin"
echo "2. Add APP_ENCRYPTION_KEY and APP_PASSWORD_ENC to your .env file"
echo "3. Run ./start_mcp.sh to start the server in stdio mode"
echo ""
echo "For more information, see the README.md file."
echo "========================================"
echo ""
