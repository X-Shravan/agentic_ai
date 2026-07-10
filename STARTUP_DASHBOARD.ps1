# Dashboard Startup Script for Windows (PowerShell)
# This script starts both the API server and React dashboard

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  AI Exam Surveillance Dashboard - Startup Script  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if npm is installed
try {
    $npmVersion = npm --version 2>&1
    Write-Host "✅ Node.js/npm found: npm $npmVersion" -ForegroundColor Green
    $npmAvailable = $true
} catch {
    Write-Host "⚠️  npm is not installed or not in PATH" -ForegroundColor Yellow
    Write-Host "React dashboard will not auto-start"
    $npmAvailable = $false
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
Write-Host ""

# Start API Server
Write-Host "🚀 Starting API Server on port 5000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python api_server.py" -WindowStyle Normal

# Wait for API server to initialize
Write-Host "⏳ Waiting for API server to initialize (5 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Start React Dashboard if npm is available
if ($npmAvailable) {
    $npmModulesPath = Join-Path $PSScriptRoot "dashboard\react-dashboard\node_modules"
    
    if (-Not (Test-Path $npmModulesPath)) {
        Write-Host "📦 Installing React dependencies (this may take a moment)..." -ForegroundColor Yellow
        $dashboardPath = Join-Path $PSScriptRoot "dashboard\react-dashboard"
        Set-Location $dashboardPath
        npm install
        Set-Location $PSScriptRoot
    }
    
    Write-Host "🚀 Starting React Dashboard on port 3000..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\dashboard\react-dashboard'; npm start" -WindowStyle Normal
} else {
    Write-Host ""
    Write-Host "⚠️  To start React Dashboard manually:" -ForegroundColor Yellow
    Write-Host "   cd dashboard\react-dashboard" -ForegroundColor Gray
    Write-Host "   npm install (first time only)" -ForegroundColor Gray
    Write-Host "   npm start" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              ✅ Services Started!                  ║" -ForegroundColor Cyan
Write-Host "╠════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  API Server:  http://localhost:5000                ║" -ForegroundColor Green
Write-Host "║  Dashboard:   http://localhost:3000                ║" -ForegroundColor Green
Write-Host "║  WebSocket:   ws://localhost:5000                  ║" -ForegroundColor Green
Write-Host "╠════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Dashboard will open automatically in browser      ║" -ForegroundColor White
Write-Host "║  Check browser console (F12) for connection status║" -ForegroundColor White
Write-Host "║                                                    ║" -ForegroundColor White
Write-Host "║  To stop: Close both terminal windows             ║" -ForegroundColor White
Write-Host "╚════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 10
