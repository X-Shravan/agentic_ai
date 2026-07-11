#!/usr/bin/env python
"""
Dashboard Connection Verification Script
Tests the API server and WebSocket connection
"""

import requests
import socket
import sys
from time import sleep

def check_port_open(host, port, name):
    """Check if a port is open and listening"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"✅ {name} is listening on {host}:{port}")
            return True
        else:
            print(f"❌ {name} is NOT listening on {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Error checking {name}: {e}")
        return False

def check_api_endpoint(url, name):
    """Check if an API endpoint is responding"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {name} endpoint is responding")
            try:
                data = response.json()
                print(f"   Response: {str(data)[:100]}...")
                return True
            except:
                print(f"   Response: {response.text[:100]}...")
                return True
        else:
            print(f"❌ {name} returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {name}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {name} timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking {name}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("   AI Exam Surveillance Dashboard - Verification Script")
    print("="*60 + "\n")
    
    results = []
    
    print("🔍 Checking Services...\n")
    
    # Check API Server
    print("1️⃣ Checking API Server (port 5000)...")
    api_running = check_port_open('localhost', 5000, 'API Server')
    results.append(('API Server', api_running))
    print()
    
    # Check React Dashboard
    print("2️⃣ Checking React Dashboard (port 3000)...")
    react_running = check_port_open('localhost', 3000, 'React Dashboard')
    results.append(('React Dashboard', react_running))
    print()
    
    # Check API Endpoints
    if api_running:
        print("3️⃣ Checking API Endpoints...\n")
        
        print("   a) Health Check...")
        check_api_endpoint('http://localhost:5000/api/health', 'Health Check')
        print()
        
        print("   b) Dashboard Data...")
        check_api_endpoint('http://localhost:5000/api/dashboard', 'Dashboard Data')
        print()
        
        print("   c) Alerts...")
        check_api_endpoint('http://localhost:5000/api/alerts', 'Alerts')
        print()
        
        print("   d) Analytics Timeline...")
        check_api_endpoint('http://localhost:5000/api/analytics/timeline', 'Timeline')
        print()
        
        print("   e) Cheating Types...")
        check_api_endpoint('http://localhost:5000/api/analytics/cheating-types', 'Cheating Types')
        print()
    else:
        print("⚠️ Skipping API endpoint checks (API server not running)\n")
    
    # Summary
    print("="*60)
    print("   SUMMARY")
    print("="*60)
    
    all_good = True
    for name, status in results:
        status_icon = "✅" if status else "❌"
        status_text = "Working" if status else "Not Running"
        print(f"{status_icon} {name}: {status_text}")
        if not status:
            all_good = False
    
    print()
    
    if all_good and api_running:
        print("✅ All services are running correctly!")
        print("📊 Dashboard should be accessible at: http://localhost:3000")
    elif api_running and not react_running:
        print("⚠️  API Server is running, but React Dashboard is not started yet.")
        print("   Run: cd dashboard/react-dashboard && npm start")
    elif not api_running and react_running:
        print("⚠️  React Dashboard is running, but API Server is not started.")
        print("   Run: python api_server.py")
    else:
        print("❌ Services are not running.")
        print("   Start the API Server: python api_server.py")
        print("   Start React Dashboard: cd dashboard/react-dashboard && npm start")
    
    print()
    
    # Additional tips
    print("💡 Tips:")
    print("   • Check browser console (F12) for WebSocket connection status")
    print("   • API Server should show 'Client connected' when dashboard loads")
    print("   • Detection should show '✅ Surveillance System Started'")
    print("   • If dashboard shows no data, refresh the page (F5)")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Verification cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Verification failed: {e}")
        sys.exit(1)
