@echo off
setlocal

echo.
echo ============================================================
echo AI Exam Surveillance System - Automated Setup
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/5] Python version:
python --version
if errorlevel 1 exit /b 1

echo.
echo [2/5] Creating virtual environment...
if exist .venv (
    echo Virtual environment already exists, skipping.
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo.
echo [3/5] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo.
echo [4/5] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [5/5] Creating runtime directories...
if not exist logs mkdir logs
if not exist reports mkdir reports
if not exist evidence mkdir evidence
if not exist archived_reports mkdir archived_reports
if not exist config mkdir config
if not exist config\config.yaml copy config_template.yaml config\config.yaml >nul

echo.
echo ============================================================
echo Running system status check...
echo ============================================================
python SYSTEM_STATUS.py
if errorlevel 1 (
    echo Setup finished, but system status reported issues.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SETUP COMPLETE
echo ============================================================
echo Next steps:
echo 1. Configure email credentials in .env if report emails are needed.
echo 2. Run: python -c "from email_sender import interactive_setup; interactive_setup()"
echo 3. Run: python TEST_SETUP.py
echo 4. Start the app with your project startup command.
echo.
pause
