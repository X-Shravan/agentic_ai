#!/usr/bin/env python3
"""
Minimal Starter - Starts only the working services
Use this if you're having issues with dependencies
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def run_command(cmd, cwd=None, name="Service"):
    """Run a command and return the process"""
    try:
        print(f"▶️  Starting {name}...")
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(1)
        if process.poll() is None:
            print(f"✅ {name} started (PID: {process.pid})")
            return process
        else:
            print(f"❌ {name} failed to start")
            return None
    except Exception as e:
        print(f"❌ {name} error: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("Minimal Project Starter")
    print("="*60 + "\n")
    
    root = Path(__file__).parent
    os.chdir(root)
    
    processes = []
    
    # Start Backend
    print("[1/3] Backend (FastAPI)\n")
    backend_proc = run_command(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(root),
        name="Backend"
    )
    if backend_proc:
        processes.append(("Backend", backend_proc))
    else:
        print("⚠️  Backend failed to start\n")
    
    # Start Dashboard
    print("\n[2/3] Dashboard (Flask)\n")
    dashboard_proc = run_command(
        [sys.executable, str(root / "dashboard/app.py")],
        cwd=str(root),
        name="Dashboard"
    )
    if dashboard_proc:
        processes.append(("Dashboard", dashboard_proc))
    else:
        print("⚠️  Dashboard failed to start\n")
    
    # Start Simple API
    print("\n[3/3] Simple API Server\n")
    api_proc = run_command(
        [sys.executable, str(root / "api_simple.py")],
        cwd=str(root),
        name="Simple API"
    )
    if api_proc:
        processes.append(("Simple API", api_proc))
    else:
        print("⚠️  Simple API failed to start\n")
    
    # Show summary
    print("\n" + "="*60)
    print("✅ Services Started")
    print("="*60 + "\n")
    print("Available at:")
    print("  🌐 Backend API     : http://localhost:8000")
    print("                       Docs: http://localhost:8000/docs")
    print("  📊 Dashboard       : http://localhost:5000")
    print("  📡 Simple API      : http://localhost:8080")
    print("\n📌 Processes running:")
    for name, proc in processes:
        status = "✓" if proc.poll() is None else "✗"
        print(f"  {status} {name} (PID: {proc.pid})")
    
    print(f"\n⚠️  Press Ctrl+C to stop all services\n")
    
    # Monitor
    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n⚠️  {name} stopped (exit code: {proc.returncode})")
    except KeyboardInterrupt:
        print("\n\n⛔ Shutting down...\n")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=2)
                print(f"✓ {name} stopped")
            except:
                proc.kill()
                print(f"✓ {name} killed")
        print("\n")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
