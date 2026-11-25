from __future__ import annotations
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading
import time
from datetime import datetime
from collections import deque, defaultdict
import base64
import io
import os
import math

# Import surveillance system
import sys
from importlib.util import find_spec
from pathlib import Path

def configure_console_output():
    """Avoid UnicodeEncodeError for emoji logs on Windows/piped output."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


configure_console_output()
sys.path.insert(0, str(Path(__file__).parent))

missing_cv_dependencies = [
    package_name
    for package_name in ("cv2", "ultralytics")
    if find_spec(package_name) is None
]

if missing_cv_dependencies:
    ExamSurveillanceSystem = None
    print(
        "⚠️ Could not import surveillance system: "
        f"missing {', '.join(missing_cv_dependencies)}"
    )
else:
    try:
        import cv2
        import ultralytics  # noqa: F401

        if not hasattr(cv2, "imshow"):
            raise ImportError("cv2.imshow is unavailable; install opencv-python instead of opencv-python-headless")

        from backend.legacy_runner import ExamSurveillanceSystem
    except Exception as import_error:
        ExamSurveillanceSystem = None
        print(f"⚠️ Could not import surveillance system: {import_error}")

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
        self.camera_status = "Starting"
        self.camera_message = "Starting surveillance camera feed"
        self.synthetic_frame_count = 0

dashboard_data = DashboardData()
surveillance_system = None

PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)

def placeholder_frame_bytes(message="Waiting for camera"):
    """Return a tiny JPEG placeholder so the dashboard does not receive 404s."""
    return PLACEHOLDER_JPEG


def generate_synthetic_frame_bytes(message="Simulation camera active"):
    """Generate a JPEG simulation frame when the full CV pipeline is unavailable."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return placeholder_frame_bytes(message)

    dashboard_data.synthetic_frame_count += 1
    tick = dashboard_data.synthetic_frame_count
    height, width = 640, 640
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    for y in range(height):
        shade = int(24 + (y / height) * 36)
        frame[y, :] = (shade, shade, shade + 10)

    cv2.rectangle(frame, (28, 28), (width - 28, 112), (35, 70, 55), -1)
    cv2.rectangle(frame, (28, 28), (width - 28, 112), (90, 170, 135), 2)
    cv2.putText(frame, "AI Exam Surveillance", (65, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (220, 255, 230), 2)
    cv2.putText(frame, message[:58], (65, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (190, 225, 255), 1)

    for row, desk_y in enumerate([230, 390, 540]):
        cv2.rectangle(frame, (60, desk_y), (width - 60, desk_y + 35), (75, 55, 40), -1)
        cv2.line(frame, (60, desk_y), (width - 60, desk_y), (120, 90, 70), 2)
        for col in range(4):
            base_x = 115 + col * 135
            wobble = int(8 * math.sin((tick / 12.0) + row + col))
            cv2.circle(frame, (base_x + wobble, desk_y - 42), 22, (80, 150, 210), -1)
            cv2.rectangle(frame, (base_x - 24 + wobble, desk_y - 20), (base_x + 24 + wobble, desk_y + 25), (70, 115, 185), -1)
            cv2.rectangle(frame, (base_x - 44 + wobble, desk_y - 75), (base_x + 44 + wobble, desk_y + 28), (0, 190, 80), 2)
            cv2.putText(frame, f"ID {row * 4 + col + 1}", (base_x - 31 + wobble, desk_y - 82), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 120), 1)

    phone_x = 95 + int((tick * 4) % (width - 190))
    cv2.rectangle(frame, (phone_x, 160), (phone_x + 24, 205), (40, 40, 230), -1)
    cv2.rectangle(frame, (phone_x, 160), (phone_x + 24, 205), (255, 255, 255), 1)
    cv2.putText(frame, "SIM LIVE", (width - 145, height - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    ok, buffer = cv2.imencode('.jpg', frame)
    if not ok:
        return placeholder_frame_bytes(message)
    return buffer.tobytes()


class DashboardHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

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
                    "monitoring": "Active" if surveillance_system else "Simulation",
                    "detection": "Running" if surveillance_system else "Fallback",
                    "camera": dashboard_data.camera_status,
                    "ai_model": "Initialized" if surveillance_system else "Unavailable"
                },
                'camera_message': dashboard_data.camera_message,
                'timestamp': datetime.now().isoformat()
            })
        elif path == '/api/analytics/timeline':
            self.send_json({
                'timestamps': list(dashboard_data.timestamps),
                'alert_counts': list(dashboard_data.alert_counts)
            })
        elif path == '/api/analytics/cheating-types':
            self.send_json({
                'cheating_types': dict(dashboard_data.cheating_types),
                'total_alerts': len(dashboard_data.alerts),
                'timestamp': datetime.now().isoformat()
            })
        elif path == '/api/camera/frame':
            if dashboard_data.current_frame_b64:
                frame_data = base64.b64decode(dashboard_data.current_frame_b64)
            elif dashboard_data.camera_status == "Simulation":
                frame_data = generate_synthetic_frame_bytes(dashboard_data.camera_message)
            else:
                frame_data = placeholder_frame_bytes(dashboard_data.camera_message)
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('Access-Control-Expose-Headers', 'X-Camera-Status, X-Camera-Message')
            self.send_header('X-Camera-Status', dashboard_data.camera_status)
            self.send_header('X-Camera-Message', dashboard_data.camera_message)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(frame_data)
        elif path.startswith('/socket.io/'):
            self.send_json({'ok': False, 'message': 'Socket.IO is disabled in api_simple.py; HTTP polling is active.'})
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
        if ExamSurveillanceSystem is None:
            dashboard_data.camera_status = "Simulation"
            dashboard_data.camera_message = (
                "Surveillance backend unavailable; using dashboard simulation feed. "
                f"Missing/unavailable dependencies: {', '.join(missing_cv_dependencies) or 'import error'}"
            )
            print(f"⚠️ {dashboard_data.camera_message}")
            return

        surveillance_system = ExamSurveillanceSystem(config_path="backend/core/config.yaml", demo_mode=True)
        
        if not surveillance_system.start():
            dashboard_data.camera_status = "Simulation"
            dashboard_data.camera_message = "Failed to start camera source; using dashboard simulation feed"
            print(f"❌ {dashboard_data.camera_message}")
            return
        
        print("✅ Surveillance System Started")
        if getattr(surveillance_system.surveillance_agent, "synthetic_mode", False):
            dashboard_data.camera_status = "Simulation"
            dashboard_data.camera_message = getattr(
                surveillance_system.surveillance_agent,
                "last_error",
                "Using synthetic simulation camera feed"
            )
        else:
            dashboard_data.camera_status = "Connected"
            dashboard_data.camera_message = getattr(
                surveillance_system.surveillance_agent,
                "source_label",
                "Camera feed connected"
            )
        
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
                        import cv2
                        if getattr(surveillance_system.surveillance_agent, "synthetic_mode", False):
                            dashboard_data.camera_status = "Simulation"
                            dashboard_data.camera_message = getattr(
                                surveillance_system.surveillance_agent,
                                "last_error",
                                "Using synthetic simulation camera feed"
                            )
                        else:
                            dashboard_data.camera_status = "Connected"
                            dashboard_data.camera_message = getattr(
                                surveillance_system.surveillance_agent,
                                "source_label",
                                "Camera feed connected"
                            )
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
    port = int(os.getenv("SIMPLE_API_PORT", "8080"))
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f"🚀 API Server running on http://localhost:{port}")
    print("📊 Dashboard: http://localhost:3000")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.shutdown()