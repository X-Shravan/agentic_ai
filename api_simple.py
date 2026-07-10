from __future__ import annotations
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading
import time
from datetime import datetime
from collections import deque, defaultdict
import cv2
import base64
import io

# Import surveillance system
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from main import ExamSurveillanceSystem
except:
    print("⚠️ Could not import surveillance system")

# ===================================================
# SIMPLE HTTP SERVER (NO FLASK REQUIRED)
# ===================================================

class DashboardData:
    def __init__(self):
        self.total_students = 0
        self.active_ids = []
        self.alerts = []
        self.alert_history = deque(maxlen=100)
        self.cheating_types = defaultdict(int)
        self.timestamps = deque(maxlen=100)
        self.alert_counts = deque(maxlen=100)
        self.current_frame = None
        self.current_frame_b64 = None
        self.monitoring_start_time = datetime.now()
        self.tracks_with_frames = []  # Store track info for drawing

dashboard_data = DashboardData()
surveillance_system = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/api/health':
            self.send_json({
                'status': 'online',
                'timestamp': datetime.now().isoformat()
            })
        elif path == '/api/dashboard':
            elapsed = (datetime.now() - dashboard_data.monitoring_start_time).total_seconds()
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            
            self.send_json({
                'total_students': dashboard_data.total_students,
                'active_ids': len(dashboard_data.active_ids),
                'total_alerts': len(dashboard_data.alerts),
                'normal_students': max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
                'alerts': dashboard_data.alerts,
                'cheating_types': dict(dashboard_data.cheating_types),
                'monitoring_time': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
                'system_status': {
                    "monitoring": "Active",
                    "detection": "Running",
                    "camera": "Connected",
                    "ai_model": "Initialized"
                },
                'timestamp': datetime.now().isoformat()
            })
        elif path == '/api/analytics/timeline':
            self.send_json({
                'timestamps': list(dashboard_data.timestamps),
                'alert_counts': list(dashboard_data.alert_counts)
            })
        elif path == '/api/camera/frame':
            if dashboard_data.current_frame_b64:
                frame_data = base64.b64decode(dashboard_data.current_frame_b64)
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(frame_data)
            else:
                self.send_error(404, 'No frame available')
        else:
            self.send_error(404, 'Not Found')
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # Suppress logging

def surveillance_loop():
    """Run surveillance system and update dashboard data"""
    global surveillance_system, dashboard_data
    
    print("🚀 Starting Surveillance System...")
    
    try:
        surveillance_system = ExamSurveillanceSystem(config_path="config/config.yaml", demo_mode=True)
        
        if not surveillance_system.start():
            print("❌ Failed to start surveillance system")
            return
        
        print("✅ Surveillance System Started")
        
        frame_count = 0
        
        while True:
            results = surveillance_system.process_frame()
            
            if not results:
                time.sleep(0.01)
                continue
            
            # Extract data from results
            for cam_id, data in results.items():
                tracks = data.get("tracks", [])
                scores = data.get("scores", {})
                frame = data.get("frame")
                
                # Update stats
                dashboard_data.total_students = len(tracks)
                dashboard_data.active_ids = [t.track_id for t in tracks]
                
                # Process scores and alerts
                current_alerts = []
                for tid, score_data in scores.items():
                    label = score_data.get("label", "Normal")
                    situation = score_data.get("situation", "Normal")
                    score = score_data.get("score", 0)
                    
                    # Track cheating types
                    if "Alert" in label or "Suspicious" in label:
                        current_alerts.append({
                            "id": tid,
                            "type": situation,
                            "severity": "HIGH" if "Alert" in label else "MEDIUM",
                            "timestamp": datetime.now().isoformat(),
                            "score": score
                        })
                        
                        # Count cheating types
                        if situation == "Using Mobile":
                            dashboard_data.cheating_types["Using Mobile"] += 1
                        elif situation == "Looking Around":
                            dashboard_data.cheating_types["Looking Around"] += 1
                        elif situation == "Looking to Copy":
                            dashboard_data.cheating_types["Looking to Copy"] += 1
                        elif situation == "Leaning":
                            dashboard_data.cheating_types["Leaning"] += 1
                
                # Update alerts
                dashboard_data.alerts = current_alerts[-3:]  # Keep last 3
                dashboard_data.alert_history.extend(current_alerts)
                
                # Update timestamps and counts
                dashboard_data.timestamps.append(datetime.now().isoformat())
                dashboard_data.alert_counts.append(len(current_alerts))
                
                # Store frame for streaming with detection visualization
                if frame is not None:
                    try:
                        # Draw bounding boxes on frame
                        annotated_frame = frame.copy()
                        for track in tracks:
                            x1, y1, x2, y2 = map(int, track.bbox)
                            
                            # Determine color based on alert status
                            if any(alert['id'] == track.track_id for alert in current_alerts):
                                color = (0, 0, 255)  # Red for alerts
                            else:
                                color = (0, 255, 0)  # Green for normal
                            
                            # Draw bounding box
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                            
                            # Draw ID label
                            cv2.putText(annotated_frame, f"ID: {track.track_id}", 
                                      (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        
                        # Encode frame
                        _, buffer = cv2.imencode('.jpg', annotated_frame)
                        dashboard_data.current_frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    except Exception as e:
                        print(f"Error encoding frame: {e}")
            
            frame_count += 1
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n⚠️ Surveillance loop interrupted")
    except Exception as e:
        print(f"❌ Error in surveillance loop: {e}")
    finally:
        if surveillance_system:
            surveillance_system.stop()
            print("🛑 Surveillance system stopped")

if __name__ == '__main__':
    print("🔧 Starting AI Exam Surveillance Dashboard API Server...")
    
    # Start surveillance system in background thread
    surveillance_thread = threading.Thread(target=surveillance_loop, daemon=True)
    surveillance_thread.start()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', 5000), DashboardHandler)
    print("🚀 API Server running on http://localhost:5000")
    print("📊 Dashboard: http://localhost:3000")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.shutdown()