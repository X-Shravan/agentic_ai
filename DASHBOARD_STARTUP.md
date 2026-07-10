# Dashboard Startup Guide

## ✅ Issues Fixed

1. **CORS Configuration**: Properly configured Flask-SocketIO with CORS for WebSocket communication
2. **Background Thread Context**: Fixed Flask app context for SocketIO emissions from background thread
3. **WebSocket Real-Time Updates**: React app now uses SocketIO for real-time data updates instead of just HTTP polling
4. **Error Handling**: Added proper error handling and logging in surveillance loop

## 🚀 How to Start

### Option 1: Automated Startup (Recommended)

**On Windows (PowerShell):**
```powershell
# Run from the mini project directory
.\STARTUP_DASHBOARD.ps1
```

**On Windows (CMD):**
```cmd
# Run from the mini project directory
.\STARTUP_DASHBOARD.bat
```

### Option 2: Manual Startup

**Step 1: Start the API Server (Terminal 1)**
```bash
python api_server.py
```

You should see:
```
🔧 Starting AI Exam Surveillance Dashboard API Server...
🚀 Starting Surveillance System...
✅ Surveillance System Started
🚀 API Server running on http://localhost:5000
📊 Dashboard: http://localhost:3000
```

**Step 2: Install React Dependencies (Terminal 2) - ONLY FIRST TIME**
```bash
cd dashboard/react-dashboard
npm install
```

**Step 3: Start React Dashboard (Terminal 2)**
```bash
cd dashboard/react-dashboard
npm start
```

The dashboard will automatically open at `http://localhost:3000`

## 🔍 What to Look For

### Console Logs

**API Server Console:**
- ✅ `Surveillance System Started` - Detection is running
- ✅ `Client connected` - Dashboard frontend connected
- ✅ Real-time updates with student counts and alerts

**Browser Console (F12 in Dashboard):**
- ✅ `Connected to WebSocket` - Real-time connection established
- ✅ `Received update:` - Getting live data from API

### Dashboard Display

The dashboard should show:
- 📊 System Status: All indicators should be green (Running/Connected/Initialized)
- 👥 Student Count: Shows number of students detected
- 🚨 Alerts: Shows any detected suspicious behavior
- 📈 Analytics: Charts showing cheating type distribution

## 🐛 Troubleshooting

### Dashboard Not Showing Data

1. **Check API Server is Running**
   ```bash
   netstat -ano | findstr :5000
   ```
   Should show process listening on port 5000

2. **Check WebSocket Connection**
   - Open browser Developer Tools (F12)
   - Go to Network → WS tab
   - Should see connection to `localhost:5000`

3. **Check for CORS Errors**
   - Browser console should not show CORS errors
   - If seen, check that CORS is enabled in api_server.py

4. **Restart Everything**
   - Stop both API server and React app
   - Restart API server first
   - Wait 5 seconds
   - Restart React app

### API Server Issues

1. **"Failed to start surveillance system"**
   - Check camera connection (if not in demo mode)
   - Check YOLO models are downloaded
   - Check config.yaml is valid

2. **Port Already in Use**
   ```bash
   # Kill process on port 5000
   netstat -ano | findstr :5000
   taskkill /PID <PID> /F
   ```

3. **Module Import Errors**
   - Ensure all dependencies are installed
   - Check virtual environment is activated

## 📝 Configuration

### API Port
Edit `api_server.py` - line at bottom:
```python
socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### React Dashboard Port
Edit `dashboard/react-dashboard/.env` or modify `package.json` scripts

### Socket Connection
In `App.js`, modify:
```javascript
const SOCKET_URL = 'http://localhost:5000';
```

## 📊 Features Now Working

✅ Real-time detection and alerts  
✅ Live WebSocket updates (no polling delay)  
✅ System status monitoring  
✅ Cheating type analytics  
✅ Alert history  
✅ Frame capture  
✅ Student tracking  

## 🔗 Access Points

- **Dashboard UI**: http://localhost:3000
- **API Base**: http://localhost:5000/api
- **API Health**: http://localhost:5000/api/health
- **Dashboard Data**: http://localhost:5000/api/dashboard
- **Alerts History**: http://localhost:5000/api/alerts
- **WebSocket**: ws://localhost:5000

## 💡 Tips

1. First run may take a few seconds to load YOLO models
2. Keep both terminals open while using dashboard
3. Logs show real-time detection details
4. React dashboard auto-refreshes with new data
5. System status updates every 25 seconds via WebSocket ping

---
**Issues Fixed**: Proper CORS configuration, WebSocket context, SocketIO async mode, Flask app context for background threads
