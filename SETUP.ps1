# ═══════════════════════════════════════════════════════════════════════════
# AI Exam Surveillance System - Automated Setup PowerShell Script
# This script automates the entire setup process for Windows PowerShell
# Usage: .\SETUP.ps1
# ═══════════════════════════════════════════════════════════════════════════

Write-Host "`n"
Write-Host "╔" + "═"*77 + "╗"
Write-Host "║" + " "*77 + "║"
Write-Host "║" + "  AI SURVEILLANCE SYSTEM SETUP - PowerShell Installer".PadRight(77) + "║"
Write-Host "║" + " "*77 + "║"
Write-Host "╚" + "═"*77 + "╝"
Write-Host "`n"

$ErrorActionPreference = "Stop"

# Step 1: Check Python
Write-Host "[1/5] Checking Python installation..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion`n"
}
catch {
    Write-Host "❌ ERROR: Python is not installed or not in PATH`n"
    Write-Host "Please install Python 3.10 from: https://www.python.org/downloads/"
    Write-Host "⚠️  IMPORTANT: Check 'Add Python to PATH' during installation`n"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: Create Virtual Environment
Write-Host "[2/5] Creating virtual environment..."
if (Test-Path ".venv") {
    Write-Host "⏭️  Virtual environment already exists, skipping...`n"
}
else {
    try {
        python -m venv .venv
        Write-Host "✅ Virtual environment created`n"
    }
    catch {
        Write-Host "❌ ERROR: Failed to create virtual environment`n"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Step 3: Activate Virtual Environment
Write-Host "[3/5] Activating virtual environment..."
try {
    & ".\.venv\Scripts\Activate.ps1"
    Write-Host "✅ Virtual environment activated`n"
}
catch {
    Write-Host "❌ ERROR: Failed to activate virtual environment`n"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 4: Install Requirements
Write-Host "[4/5] Installing required packages..."
Write-Host "This may take 5-10 minutes, please wait...`n"
try {
    pip install -r requirements.txt
    Write-Host "`n✅ All packages installed successfully`n"
}
catch {
    Write-Host "`n❌ ERROR: Failed to install packages`n"
    Write-Host "Try running manually:"
    Write-Host "  pip install -r requirements.txt`n"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 5: Create Directories
Write-Host "[5/5] Creating data directories..."
$directories = @("logs", "reports", "evidence", "archived_reports")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "✅ Directories created`n"

# System Check
Write-Host "═"*77
Write-Host "Checking system status..."
Write-Host "═"*77
python SYSTEM_STATUS.py

Write-Host "`n"
Write-Host "═"*77
Write-Host "✅ SETUP COMPLETE!"
Write-Host "═"*77
Write-Host "`n"
Write-Host "📋 NEXT STEPS:`n"
Write-Host "1. Setup Email Configuration (One Time):"
Write-Host "   python setup_wizard.py`n"
Write-Host "2. Read the User Guide:"
Write-Host "   README_REPORTS_EMAIL.md`n"
Write-Host "3. Start Monitoring:"
Write-Host "   python main.py`n"
Write-Host "═"*77
Write-Host "`n"

Read-Host "Press Enter to exit"
