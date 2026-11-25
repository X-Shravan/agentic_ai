#!/usr/bin/env python3
"""
Master Runner Script - Launches All Project Components
Frontend (React), Backend (FastAPI), Dashboard (Flask), and Services

Run this file to start the entire agentic_ai_version1 project
"""

import os
import sys
import subprocess
import time
import threading
import platform
import shutil
import webbrowser
import urllib.request
from pathlib import Path
from datetime import datetime


def configure_console_output():
    """Avoid UnicodeEncodeError for icons/box drawing on Windows terminals and pipes."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


configure_console_output()


def get_utf8_env():
    """Return an environment that keeps Python child process logs UTF-8 safe."""
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def log_process_failure(name, process):
    """Print helpful output when a child service exits during startup."""
    if process is None or process.poll() is None:
        return

    log_error(f"{name} failed to stay running (exit code: {process.returncode})")
    try:
        stdout, stderr = process.communicate(timeout=1)
    except Exception:
        return

    if stdout:
        print(f"\n--- {name} stdout ---\n{stdout[-2000:]}")
    if stderr:
        print(f"\n--- {name} stderr ---\n{stderr[-2000:]}")

# ANSI Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def log_info(msg):
    """Log info message"""
    print(f"{Colors.OKBLUE}[INFO]{Colors.ENDC} {msg}")


def log_success(msg):
    """Log success message"""
    print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {msg}")


def log_warning(msg):
    """Log warning message"""
    print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {msg}")


def log_error(msg):
    """Log error message"""
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {msg}")


def log_header(msg):
    """Log header message"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}{Colors.ENDC}\n")


def get_project_root():
    """Get the project root directory"""
    return Path(__file__).parent.absolute()


def get_python_executable(project_root):
    """Resolve the virtual environment Python interpreter if present, else fallback to sys.executable."""
    if platform.system() == "Windows":
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_root / ".venv" / "bin" / "python"
    
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def get_npm_command():
    """Return the npm executable path/name that works with subprocess on Windows."""
    if platform.system() == "Windows":
        return shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
    return shutil.which("npm") or "npm"


def wait_for_http(url, timeout=30):
    """Wait until an HTTP endpoint responds successfully."""
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception as e:
            last_error = e
            time.sleep(1)
    if last_error:
        log_warning(f"Timed out waiting for {url}: {last_error}")
    return False


def check_python_installed():
    """Check if Python is installed"""
    log_info("Checking Python installation...")
    try:
        py_exe = get_python_executable(get_project_root())
        result = subprocess.run([py_exe, "--version"], capture_output=True, text=True)
        log_success(f"Python {result.stdout.strip()} found ({py_exe})")
        return True
    except Exception as e:
        log_error(f"Python not found: {e}")
        return False


def check_nodejs_installed():
    """Check if Node.js and npm are installed"""
    log_info("Checking Node.js installation...")
    node_available = False
    npm_available = False
    npm_command = get_npm_command()

    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            log_success(f"Node.js {result.stdout.strip()} found")
            node_available = True
        else:
            log_warning("Node.js command returned a non-zero exit code")
    except Exception as e:
        log_warning(f"Node.js not found: {e} - Frontend will not run")
        return False

    log_info("Checking npm installation...")
    try:
        result = subprocess.run([npm_command, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            log_success(f"npm {result.stdout.strip()} found")
            npm_available = True
        else:
            log_warning("npm command returned a non-zero exit code")
    except Exception as e:
        log_warning(f"npm not found: {e} - Frontend will be skipped")

    if node_available and npm_available:
        return True

    log_warning("Frontend dependencies are unavailable - skipping React frontend")
    return False


def install_python_requirements(project_root):
    """Install Python requirements"""
    log_header("Installing Python Requirements")
    
    requirements_file = project_root / "requirements.txt"
    if not requirements_file.exists():
        log_error(f"requirements.txt not found at {requirements_file}")
        return False
    
    try:
        log_info(f"Installing from {requirements_file}...")
        py_exe = get_python_executable(project_root)
        subprocess.run(
            [py_exe, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True
        )
        log_success("Python requirements installed")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to install Python requirements: {e}")
        return False


def install_frontend_dependencies(project_root):
    """Install frontend dependencies"""
    log_header("Installing Frontend Dependencies")
    
    frontend_dir = project_root / "frontend"
    package_json = frontend_dir / "package.json"
    
    if not package_json.exists():
        log_warning(f"Frontend package.json not found at {package_json}")
        return False
    
    try:
        log_info("Installing Node.js dependencies...")
        subprocess.run(
            [get_npm_command(), "install"],
            cwd=str(frontend_dir),
            check=True
        )
        log_success("Frontend dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to install frontend dependencies: {e}")
        return False
    except FileNotFoundError:
        log_error("npm not found. Please install Node.js")
        return False


def start_backend(project_root):
    """Start FastAPI Backend"""
    log_header("Starting Backend Server (FastAPI)")
    
    backend_main = project_root / "backend" / "main.py"
    
    if not backend_main.exists():
        log_error(f"Backend main.py not found at {backend_main}")
        return None
    
    try:
        log_info("Starting FastAPI backend on http://localhost:8000")
        py_exe = get_python_executable(project_root)
        process = subprocess.Popen(
            [py_exe, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=get_utf8_env()
        )
        time.sleep(2)
        if process.poll() is not None:
            log_process_failure("Backend server", process)
            return None
        log_success("Backend server started (PID: {})".format(process.pid))
        return process
    except Exception as e:
        log_error(f"Failed to start backend: {e}")
        return None


def start_frontend(project_root):
    """Start React Frontend"""
    log_header("Starting Frontend (React)")
    
    frontend_dir = project_root / "frontend"
    package_json = frontend_dir / "package.json"
    
    if not package_json.exists():
        log_warning(f"Frontend package.json not found")
        return None
    
    try:
        log_info("Starting React frontend on http://localhost:3000")
        frontend_env = {
            **get_utf8_env(),
            "BROWSER": "none",
            "HOST": "127.0.0.1",
            "PORT": "3000",
            "CI": "true",
        }
        process = subprocess.Popen(
            [get_npm_command(), "start"],
            cwd=str(frontend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=frontend_env
        )
        time.sleep(3)
        if process.poll() is not None:
            log_process_failure("Frontend", process)
            return None
        if not wait_for_http("http://127.0.0.1:3000", timeout=30):
            log_warning("Frontend process is running but did not respond on http://127.0.0.1:3000 yet")
        log_success("Frontend started (PID: {})".format(process.pid))
        return process
    except Exception as e:
        log_error(f"Failed to start frontend: {e}")
        return None


def start_dashboard(project_root):
    """Start Flask Dashboard"""
    log_header("Starting Dashboard (Flask)")
    
    dashboard_app = project_root / "dashboard" / "app.py"
    
    if not dashboard_app.exists():
        log_warning(f"Dashboard app.py not found at {dashboard_app}")
        return None
    
    try:
        log_info("Starting Flask dashboard on http://localhost:5000")
        py_exe = get_python_executable(project_root)
        process = subprocess.Popen(
            [py_exe, str(dashboard_app)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**get_utf8_env(), "FLASK_APP": str(dashboard_app), "FLASK_ENV": "development"}
        )
        time.sleep(2)
        if process.poll() is not None:
            log_process_failure("Dashboard", process)
            return None
        log_success("Dashboard started (PID: {})".format(process.pid))
        return process
    except Exception as e:
        log_error(f"Failed to start dashboard: {e}")
        return None


def start_simple_api(project_root):
    """Start Simple API Server"""
    log_header("Starting Simple API Server")
    
    api_file = project_root / "api_simple.py"
    
    if not api_file.exists():
        log_warning(f"api_simple.py not found at {api_file}")
        return None
    
    try:
        log_info("Starting Simple API server on http://localhost:8080")
        py_exe = get_python_executable(project_root)
        process = subprocess.Popen(
            [py_exe, str(api_file)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=get_utf8_env()
        )
        time.sleep(2)
        if process.poll() is not None:
            log_process_failure("Simple API server", process)
            return None
        log_success("Simple API server started (PID: {})".format(process.pid))
        return process
    except Exception as e:
        log_error(f"Failed to start Simple API server: {e}")
        return None


def open_browser():
    """Open project URLs in browser"""
    log_info("Opening project in browser...")
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:3000")  # Frontend
    except Exception as e:
        log_warning(f"Could not open browser: {e}")


def show_startup_summary(backend_proc, frontend_proc, dashboard_proc, api_proc):
    """Show startup summary with URLs"""
    log_header("Project Started Successfully!")
    
    print(f"{Colors.BOLD}Available Services:{Colors.ENDC}\n")
    
    if frontend_proc and frontend_proc.poll() is None:
        print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Frontend (React)    : {Colors.OKCYAN}http://localhost:3000{Colors.ENDC}")
    else:
        print(f"  {Colors.FAIL}✗{Colors.ENDC} Frontend (React)    : Not running")
    
    if backend_proc and backend_proc.poll() is None:
        print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Backend (FastAPI)   : {Colors.OKCYAN}http://localhost:8000{Colors.ENDC}")
        print(f"                         API Docs: {Colors.OKCYAN}http://localhost:8000/docs{Colors.ENDC}")
    else:
        print(f"  {Colors.FAIL}✗{Colors.ENDC} Backend (FastAPI)   : Not running")
    
    if dashboard_proc and dashboard_proc.poll() is None:
        print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Dashboard (Flask)   : {Colors.OKCYAN}http://localhost:5000{Colors.ENDC}")
    else:
        print(f"  {Colors.FAIL}✗{Colors.ENDC} Dashboard (Flask)   : Not running")
    
    if api_proc and api_proc.poll() is None:
        print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Simple API Server   : {Colors.OKCYAN}http://localhost:8080{Colors.ENDC}")
    else:
        print(f"  {Colors.FAIL}✗{Colors.ENDC} Simple API Server   : Not running")
    
    print(f"\n{Colors.BOLD}Timestamp:{Colors.ENDC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.WARNING}Press Ctrl+C to stop all services{Colors.ENDC}\n")


def monitor_processes(processes):
    """Monitor running processes"""
    while True:
        try:
            time.sleep(5)
            for name, proc in processes.items():
                if proc and proc.poll() is not None:
                    log_warning(f"{name} has stopped (exit code: {proc.returncode})")
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_error(f"Error monitoring processes: {e}")


def cleanup_processes(processes):
    """Cleanup and terminate all processes"""
    log_header("Shutting Down Services")
    
    for name, proc in processes.items():
        if proc and proc.poll() is None:
            try:
                log_info(f"Stopping {name}...")
                if platform.system() == "Windows":
                    proc.terminate()
                else:
                    proc.terminate()
                proc.wait(timeout=5)
                log_success(f"{name} stopped")
            except subprocess.TimeoutExpired:
                log_warning(f"{name} did not stop gracefully, killing...")
                proc.kill()
            except Exception as e:
                log_error(f"Error stopping {name}: {e}")
    
    log_success("All services shut down")


def main():
    """Main entry point"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Agentic AI Exam Surveillance - Project Launcher     ║")
    print("║  Starting All Services (Frontend, Backend, Dashboard) ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")
    
    # Get project root
    project_root = get_project_root()
    log_info(f"Project root: {project_root}\n")
    
    # Check prerequisites
    log_header("Checking Prerequisites")
    
    if not check_python_installed():
        log_error("Python is required to run this project")
        return 1
    
    nodejs_available = check_nodejs_installed()
    
    # Install dependencies
    log_info("Installing dependencies...")
    install_python_requirements(project_root)
    
    if nodejs_available:
        install_frontend_dependencies(project_root)
    
    # Start services
    processes = {}
    
    backend_proc = start_backend(project_root)
    processes["Backend (FastAPI)"] = backend_proc
    
    if nodejs_available:
        frontend_proc = start_frontend(project_root)
        processes["Frontend (React)"] = frontend_proc
    else:
        processes["Frontend (React)"] = None
    
    dashboard_proc = start_dashboard(project_root)
    processes["Dashboard (Flask)"] = dashboard_proc
    
    api_proc = start_simple_api(project_root)
    processes["Simple API Server"] = api_proc
    
    # Show summary
    show_startup_summary(backend_proc, frontend_proc if nodejs_available else None, dashboard_proc, api_proc)
    
    # Open browser
    if nodejs_available:
        open_browser()
    
    # Monitor processes
    try:
        monitor_processes(processes)
    except KeyboardInterrupt:
        print("\n")
        cleanup_processes(processes)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        sys.exit(1)
