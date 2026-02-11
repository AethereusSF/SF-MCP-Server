@echo off
REM ========================================
REM Salesforce MCP Server Setup Script
REM ========================================
REM This script will:
REM 1. Create a Python virtual environment
REM 2. Install all required dependencies
REM 3. Test the server installation
REM ========================================

cd /d "%~dp0"

echo.
echo ========================================
echo Salesforce MCP Server Setup
echo ========================================
echo.

REM Check if Python is installed (try "python" first, then "py" launcher)
echo [1/4] Checking Python installation...
set PYTHON_CMD=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=py
    )
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11 or higher from https://www.python.org
    pause
    exit /b 1
)

%PYTHON_CMD% --version
echo Python found!
echo.

REM Create virtual environment
echo [2/4] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists. Skipping creation.
) else (
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
)
echo.

REM Install dependencies (using venv's Python directly - no activation needed)
echo [3/4] Installing dependencies from requirements.txt...
echo Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    pause
    exit /b 1
)

echo Installing requirements...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

REM Setup .env file if not exists
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env >nul 2>&1
    if errorlevel 1 (
        echo WARNING: Could not create .env file. Please copy .env.example to .env manually.
    ) else (
        echo .env file created. Please configure it before running the server.
    )
    echo.
)

REM Test the installation
echo [4/4] Testing server installation...
echo Running dependency import tests...

venv\Scripts\python.exe -c "import mcp; print('  MCP library: OK')"
if errorlevel 1 (
    echo WARNING: MCP library test failed
)

venv\Scripts\python.exe -c "import simple_salesforce; print('  Salesforce library: OK')"
if errorlevel 1 (
    echo WARNING: Salesforce library test failed
)

venv\Scripts\python.exe -c "import cryptography; print('  Cryptography library: OK')"
if errorlevel 1 (
    echo WARNING: Cryptography library test failed
)

venv\Scripts\python.exe -c "import pydantic; print('  Pydantic library: OK')"
if errorlevel 1 (
    echo WARNING: Pydantic library test failed
)
echo.

echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Get your license key from MCP Admin
echo 2. Add APP_ENCRYPTION_KEY and APP_PASSWORD_ENC to your .env file
echo 3. Run start_mcp.bat to start the server in stdio mode
echo.
echo For more information, see the README.md file.
echo ========================================
echo.
pause
