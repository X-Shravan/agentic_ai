from __future__ import annotations
import threading
import time
import signal
import sys
import os
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import io
import base64
from collections import deque, defaultdict
from datetime import datetime

# Import surveillance system
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.legacy_runner import ExamSurveillanceSystem

# ✅ REPORT SYSTEM IMPORTS
from report_integration import initialize_report_system, log_alert_to_report, generate_session_report
from generate_pdf_report import generate_report

# ===================================================
# FLASK API SERVER
# ===================================================

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

surveillance_system = None
surveillance_thread = None
should_stop = False  # Flag to signal threads to stop

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global should_stop, surveillance_thread
    print("\n" + "="*70)
    print("⚠️  SHUTDOWN SIGNAL RECEIVED (Ctrl+C)")
    print("="*70)
    should_stop = True
    
    # Wait for surveillance thread to finish
    if surveillance_thread and surveillance_thread.is_alive():
        print("⏳ Waiting for surveillance thread to finish...")
        surveillance_thread.join(timeout=5)
        print("✅ Thread stopped")
    
    print("\n✅ Shutdown complete. Goodbye!")
    sys.exit(0)

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
        self.system_status = {
            "monitoring": "Initializing",
            "detection": "Initializing",
            "camera": "Disconnected",
            "ai_model": "Loading"
        }
        self.monitoring_start_time = datetime.now()
        self.system_running = False
        self.camera_active = False
        self.detection_active = False
        self.models_loaded = False
        self.frame_count = 0
        self.last_frame_time = None

dashboard_data = DashboardData()


def placeholder_frame_bytes(message="Waiting for camera"):
    """Return a JPEG placeholder frame instead of a 404 while Camo/webcam warms up."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, message, (95, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    ok, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes() if ok else b''


# ===================================================
# SURVEILLANCE LOOP
# ===================================================

def surveillance_loop():
    """Run surveillance system and update dashboard data"""
    global surveillance_system, dashboard_data, should_stop
    
    print("🚀 Starting Surveillance System...")
    dashboard_data.system_status["monitoring"] = "Starting"
    dashboard_data.system_status["detection"] = "Starting"
    
    try:
        surveillance_system = ExamSurveillanceSystem(config_path="backend/core/config.yaml", demo_mode=True)
        
        if not surveillance_system.start():
            print("❌ Failed to start surveillance system")
            dashboard_data.system_status["monitoring"] = "Error"
            dashboard_data.system_status["detection"] = "Error"
            dashboard_data.system_status["camera"] = "Failed"
            dashboard_data.system_status["ai_model"] = "Failed"
            return
        
        print("✅ Surveillance System Started")
        dashboard_data.system_running = True
        dashboard_data.camera_active = True
        dashboard_data.detection_active = True
        dashboard_data.models_loaded = True
        dashboard_data.system_status["monitoring"] = "Active"
        dashboard_data.system_status["detection"] = "Running"
        dashboard_data.system_status["camera"] = "Connected"
        dashboard_data.system_status["ai_model"] = "Initialized"
        
        frame_count = 0
        frame_update_interval = 5  # 🔥 Update display frame every 5 frames (reduce lag)
        
        while not should_stop:  # ✅ CHECK STOP FLAG HERE
            results = surveillance_system.process_frame()
            
            if not results:
                time.sleep(0.01)
                continue
            
            # Update real-time status
            dashboard_data.last_frame_time = datetime.now()
            dashboard_data.frame_count += 1
            
            # Extract data from results
            for cam_id, data in results.items():
                tracks = data.get("tracks", [])
                scores = data.get("scores", {})
                processed_frame = data.get("frame")  # ✅ GET PROCESSED FRAME WITH DRAWINGS
                
                print(f"[DEBUG] Processing frame with {len(tracks)} tracks")
                
                # 🔥 CRITICAL FIX: Only count confirmed active tracks
                # Filter for tracks that haven't aged out and have recent hits
                active_tracks = [t for t in tracks if hasattr(t, 'time_since_update') and t.time_since_update <= 3]
                dashboard_data.total_students = len(active_tracks)
                dashboard_data.active_ids = [t.track_id for t in active_tracks]
                
                # Process scores and alerts
                current_alerts = []
                for tid, score_data in scores.items():
                    label = score_data.get("label", "Normal")
                    situation = score_data.get("situation", "Normal")
                    score = score_data.get("score", 0)
                    
                    # ✅ INCLUDE ALL BEHAVIORS: alerts (🚨), suspicious (👀↘️), and sharing (🤝)
                    is_alert = "Alert" in label or "Suspicious" in label or "High Risk" in label or "🚨" in situation or "🤝" in situation or "👀" in situation or "↘️" in situation
                    
                    if is_alert:
                        print(f"🔴 LOGGING: ID {tid} | Status: {situation}")
                        
                        current_alerts.append({
                            "id": tid,
                            "type": situation,
                            "severity": "HIGH" if "Alert" in label or "High Risk" in label or "🚨" in situation else "MEDIUM",
                            "timestamp": datetime.now().isoformat(),
                            "score": score
                        })
                        
                        # Count ALL cheating types including Sharing
                        if "Using Mobile" in situation:
                            dashboard_data.cheating_types["Using Mobile"] += 1
                        elif "Looking Around" in situation:
                            dashboard_data.cheating_types["Looking Around"] += 1
                        elif "Looking to Copy" in situation:
                            dashboard_data.cheating_types["Looking to Copy"] += 1
                        elif "Leaning" in situation:
                            dashboard_data.cheating_types["Leaning"] += 1
                        elif "Sharing Answers" in situation:
                            dashboard_data.cheating_types["Sharing Answers"] += 1
                        
                        # ✅ SAVE ALERT IMAGE (processed frame WITH DRAWINGS AND LABELS)
                        image_filename = None
                        if processed_frame is not None:
                            timestamp_str = datetime.now().strftime("%H%M%S")
                            image_filename = f"evidence/ID{tid}_{timestamp_str}.jpg"
                            try:
                                cv2.imwrite(image_filename, processed_frame)
                                print(f"✅ Evidence saved: {image_filename} (processed frame with labels)")
                            except Exception as img_err:
                                print(f"❌ Error saving evidence: {img_err}")
                                image_filename = None
                        
                        # ✅ LOG ALERT FOR REPORT (with or without image)
                        log_alert_to_report(
                            student_id=tid,
                            behavior_type=situation,
                            timestamp=datetime.now().strftime("%H:%M:%S"),
                            image_path=image_filename
                        )
                
                # Update alerts
                dashboard_data.alerts = current_alerts[-3:]  # Keep last 3
                dashboard_data.alert_history.extend(current_alerts)
                
                # Update timestamps and counts
                dashboard_data.timestamps.append(datetime.now().isoformat())
                dashboard_data.alert_counts.append(len(current_alerts))
                
                # 🔥 Store frame for streaming - ONLY EVERY 5 FRAMES (reduce lag)
                if processed_frame is not None and frame_count % frame_update_interval == 0:
                    print(f"[DEBUG] Encoding frame for streaming (frame #{frame_count})")
                    # Reduce quality for faster encoding (70% quality = 3x faster encoding)
                    _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    dashboard_data.current_frame = base64.b64encode(buffer).decode('utf-8')
                
                # 🔥 Emit updates every frame but only update frame every 5 frames
                with app.app_context():
                    socketio.emit('surveillance_update', {
                        'total_students': dashboard_data.total_students,
                        'active_ids': len(dashboard_data.active_ids),
                        'total_alerts': len(current_alerts),
                        'normal_students': max(0, dashboard_data.total_students - len(current_alerts)),
                        'alerts': current_alerts,
                        'cheating_types': dict(dashboard_data.cheating_types),
                        'timestamp': datetime.now().isoformat()
                    }, skip_sid=None)
            
            frame_count += 1
            time.sleep(0.01)
        import traceback
        traceback.print_exc()
        dashboard_data.system_status["monitoring"] = "Error"
        dashboard_data.system_status["detection"] = "Error"
    finally:
        print("\n" + "="*70)
        print("🛑 SHUTTING DOWN SURVEILLANCE SYSTEM")
        print("="*70)
        
        dashboard_data.system_running = False
        dashboard_data.camera_active = False
        dashboard_data.detection_active = False
        dashboard_data.system_status["monitoring"] = "Stopped"
        dashboard_data.system_status["detection"] = "Stopped"
        dashboard_data.system_status["camera"] = "Disconnected"
        
        if surveillance_system:
            print("⏸️  Stopping surveillance system...")
            surveillance_system.stop()
            print("✅ Surveillance stopped")
        
        # ✅ CALCULATE MONITORING TIME
        monitoring_end = datetime.now()
        time_diff = monitoring_end - dashboard_data.monitoring_start_time
        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        monitoring_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        print("\n" + "="*70)
        print("📊 GENERATING FINAL REPORTS")
        print("="*70)
        print(f"📈 Total alerts collected: {len(dashboard_data.alert_history)}")
        print(f"📌 Total students detected: {dashboard_data.total_students}")
        print(f"⏱️  Monitoring duration: {monitoring_time_str}")
        
        # ✅ PREPARE SUMMARY DATA
        summary_data = {
            "total_students": dashboard_data.total_students,
            "active_ids": len(dashboard_data.active_ids),
            "total_alerts": len(dashboard_data.alert_history),
            "normal_students": max(0, dashboard_data.total_students - len(dashboard_data.alert_history))
        }
        
        print(f"✅ Summary data prepared: {summary_data}")
        
        # Convert alert history to list format
        alerts_list = [
            {
                "id": alert.get('id', 'N/A'),
                "type": alert.get('type', 'Unknown'),
                "time": alert.get('timestamp', 'N/A').split('T')[1][:8] if 'T' in alert.get('timestamp', '') else 'N/A',
                "image_path": alert.get('image_path', None)
            }
            for alert in list(dashboard_data.alert_history)
        ]
        
        print(f"✅ Alerts list prepared: {len(alerts_list)} alerts")
        if alerts_list:
            print(f"   First alert: {alerts_list[0]}")
        
        # ✅ GENERATE PDF REPORT (DIRECT CALL)
        print("\n🔵 Generating PDF report...")
        try:
            pdf_path = generate_report(alerts_list, summary_data)
            if pdf_path:
                print(f"✅ PDF Report saved: {pdf_path}")
                if os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path)
                    print(f"✅ File verified: {file_size} bytes")
            else:
                print("❌ PDF generation returned None")
        except Exception as pdf_error:
            print(f"❌ Error during PDF generation: {pdf_error}")
            import traceback
            traceback.print_exc()
        
        # ✅ GENERATE REPORT + SEND EMAIL (LEGACY)
        generate_session_report(
            total_students=dashboard_data.total_students,
            active_ids=len(dashboard_data.active_ids),
            total_alerts=len(dashboard_data.alert_history),
            normal_students=dashboard_data.total_students - len(dashboard_data.alert_history),
            monitoring_time=monitoring_time_str,
            send_email=True,
            clear_logs=True
        )
        
        print("🛑 Surveillance system stopped")

# ===================================================
# API ROUTES
# ===================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/counters', methods=['GET'])
def get_counter_stats():
    """Get behavior counter statistics (for debugging)"""
    if surveillance_system is None:
        return jsonify({'error': 'Surveillance system not initialized'}), 503
    
    # Get counter stats from behavior agent
    try:
        # Get the first behavior agent (for demo mode with single camera)
        if hasattr(surveillance_system, 'behavior_agents') and surveillance_system.behavior_agents:
            behavior_agent = list(surveillance_system.behavior_agents.values())[0]
            counter_stats = behavior_agent.get_counter_stats()
            return jsonify({
                'counters': counter_stats,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Behavior agent not initialized'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    """Get current dashboard data"""
    elapsed = (datetime.now() - dashboard_data.monitoring_start_time).total_seconds()
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    
    # Update real-time system status
    if dashboard_data.last_frame_time:
        time_since_frame = (datetime.now() - dashboard_data.last_frame_time).total_seconds()
        if time_since_frame > 5:
            dashboard_data.system_status["camera"] = "Disconnected"
            dashboard_data.camera_active = False
        elif not dashboard_data.camera_active and dashboard_data.system_running:
            dashboard_data.system_status["camera"] = "Connected"
            dashboard_data.camera_active = True
    
    return jsonify({
        'total_students': dashboard_data.total_students,
        'active_ids': len(dashboard_data.active_ids),
        'total_alerts': len(dashboard_data.alerts),
        'normal_students': max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
        'alerts': dashboard_data.alerts,
        'cheating_types': dict(dashboard_data.cheating_types),
        'monitoring_time': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        'system_status': dashboard_data.system_status,
        'frame_count': dashboard_data.frame_count,
        'system_running': dashboard_data.system_running,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get alert history"""
    return jsonify({
        'alerts': list(dashboard_data.alert_history),
        'total': len(dashboard_data.alert_history)
    })

@app.route('/api/analytics/timeline', methods=['GET'])
def get_timeline():
    """Get alerts over time for chart"""
    return jsonify({
        'timestamps': list(dashboard_data.timestamps),
        'alert_counts': list(dashboard_data.alert_counts)
    })

@app.route('/api/analytics/cheating-types', methods=['GET'])
def get_cheating_types():
    """Get cheating type distribution"""
    return jsonify(dict(dashboard_data.cheating_types))

@app.route('/api/camera/frame', methods=['GET'])
def get_camera_frame():
    """Get current camera frame"""
    frame_data = (
        base64.b64decode(dashboard_data.current_frame)
        if dashboard_data.current_frame
        else placeholder_frame_bytes('Waiting for Camo/mobile camera')
    )
    return send_file(io.BytesIO(frame_data), mimetype='image/jpeg')

@app.route('/api/reports/generate', methods=['POST'])
def api_generate_report():
    """Generate PDF report on demand"""
    print("\n" + "="*70)
    print("📊 API REQUEST: Generate Report")
    print("="*70)
    
    try:
        # ✅ PREPARE SUMMARY DATA
        summary_data = {
            "total_students": dashboard_data.total_students,
            "active_ids": len(dashboard_data.active_ids),
            "total_alerts": len(dashboard_data.alert_history),
            "normal_students": max(0, dashboard_data.total_students - len(dashboard_data.alert_history))
        }
        
        # Convert alert history to list format
        alerts_list = [
            {
                "id": alert.get('id', 'N/A'),
                "type": alert.get('type', 'Unknown'),
                "time": alert.get('timestamp', 'N/A').split('T')[1][:8] if 'T' in alert.get('timestamp', '') else 'N/A',
                "image_path": alert.get('image_path', None)
            }
            for alert in list(dashboard_data.alert_history)
        ]
        
        # ✅ GENERATE PDF REPORT
        print("🔵 Generating PDF report from API request...")
        pdf_path = generate_report(alerts_list, summary_data)
        
        if pdf_path and os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"✅ Report generated successfully")
            print(f"📁 Path: {pdf_path}")
            print(f"💾 Size: {file_size} bytes")
            
            return jsonify({
                'success': True,
                'message': 'Report generated successfully',
                'report_path': pdf_path,
                'file_size': file_size,
                'total_alerts': len(alerts_list),
                'total_students': dashboard_data.total_students,
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            print("❌ PDF generation failed")
            return jsonify({
                'success': False,
                'message': 'Failed to generate report',
                'error': 'PDF file was not created'
            }), 500
    
    except Exception as e:
        print(f"❌ Error in report generation: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': 'Error generating report',
            'error': str(e)
        }), 500

@app.route('/api/surveillance/stop', methods=['POST'])
def stop_surveillance():
    """Stop surveillance and generate final report"""
    print("\n" + "="*70)
    print("🛑 API REQUEST: Stop Surveillance & Generate Report")
    print("="*70)
    
    if not dashboard_data.system_running:
        return jsonify({
            'success': False,
            'message': 'Surveillance system not running'
        }), 400
    
    try:
        # Stop the surveillance system
        if surveillance_system:
            print("⏸️  Stopping surveillance system...")
            surveillance_system.stop()
            print("✅ Surveillance stopped")
        
        # Give the thread a moment to execute finally block
        time.sleep(2)
        
        # Check if PDF was generated
        reports_dir = "reports"
        if os.path.exists(reports_dir):
            files = sorted(os.listdir(reports_dir), reverse=True)
            pdf_files = [f for f in files if f.endswith('.pdf')]
            if pdf_files:
                latest_pdf = pdf_files[0]
                latest_path = os.path.join(reports_dir, latest_pdf)
                file_size = os.path.getsize(latest_path)
                
                return jsonify({
                    'success': True,
                    'message': 'Surveillance stopped and report generated',
                    'report_path': latest_path,
                    'file_size': file_size,
                    'total_alerts': len(dashboard_data.alert_history),
                    'timestamp': datetime.now().isoformat()
                }), 200
        
        return jsonify({
            'success': True,
            'message': 'Surveillance stopped',
            'total_alerts': len(dashboard_data.alert_history),
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        print(f"❌ Error stopping surveillance: {e}")
        return jsonify({
            'success': False,
            'message': 'Error stopping surveillance',
            'error': str(e)
        }), 500

@app.route('/api/reports/test', methods=['POST'])
def test_pdf_generation():
    """Test PDF generation with current data"""
    print("\n" + "="*70)
    print("🧪 TESTING PDF GENERATION")
    print("="*70)
    
    try:
        # Check reports folder
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            print(f"⚠️  Creating reports folder: {reports_dir}")
            os.makedirs(reports_dir, exist_ok=True)
        
        # Prepare test data
        test_alerts = [
            {
                "id": 1,
                "type": "Using Mobile",
                "time": "10:05:12",
                "image_path": None
            },
            {
                "id": 2,
                "type": "Looking Around",
                "time": "10:10:30",
                "image_path": None
            }
        ]
        
        test_summary = {
            "total_students": 30,
            "active_ids": 28,
            "total_alerts": 2,
            "normal_students": 26
        }
        
        print("📝 Test data prepared:")
        print(f"   • Alerts: {len(test_alerts)}")
        print(f"   • Summary: {test_summary}")
        
        # Generate test PDF
        print("🔵 Generating test PDF...")
        pdf_path = generate_report(test_alerts, test_summary)
        
        if pdf_path and os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"✅ Test PDF generated successfully!")
            print(f"📁 Location: {os.path.abspath(pdf_path)}")
            print(f"💾 Size: {file_size} bytes")
            
            return jsonify({
                'success': True,
                'message': 'Test PDF generated successfully',
                'report_path': pdf_path,
                'file_size': file_size,
                'test': True
            }), 200
        else:
            print("❌ Test PDF generation failed")
            return jsonify({
                'success': False,
                'message': 'Test PDF generation failed',
                'error': 'PDF was not created'
            }), 500
    
    except Exception as e:
        print(f"❌ Error in test PDF generation: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': 'Error in test PDF generation',
            'error': str(e)
        }), 500

# ===================================================
# WEBSOCKET EVENTS
# ===================================================

@socketio.on('connect')
def handle_connect():
    print(f"✅ Client connected")
    emit('connection_response', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    print(f"❌ Client disconnected")

@socketio.on('request_update')
def handle_update_request():
    """Send current dashboard data to requesting client"""
    emit('surveillance_update', {
        'total_students': dashboard_data.total_students,
        'active_ids': len(dashboard_data.active_ids),
        'total_alerts': len(dashboard_data.alerts),
        'normal_students': max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
        'alerts': dashboard_data.alerts,
        'cheating_types': dict(dashboard_data.cheating_types),
        'timestamp': datetime.now().isoformat()
    })

# ===================================================
# STARTUP
# ===================================================

if __name__ == '__main__':
    print("🔧 Starting AI Exam Surveillance Dashboard API Server...")
    
    # ✅ INIT REPORT SYSTEM
    initialize_report_system()

    # ===================================================
    # REGISTER GRACEFUL SHUTDOWN HANDLER
    # ===================================================
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)  # SIGTERM

    # Start surveillance system in background thread (NON-DAEMON!)
    # Important: daemon=False ensures the finally block executes on shutdown
    surveillance_thread = threading.Thread(target=surveillance_loop, daemon=False)
    surveillance_thread.start()
    
    # Start Flask server
    print("🚀 API Server running on http://localhost:5000")
    print("📊 Dashboard: http://localhost:3000")
    print("\n💡 TIP: When you stop the server (Ctrl+C), it will:")
    print("   1. Stop the surveillance loop")
    print("   2. Generate the PDF report automatically")
    print("   3. Save it to reports/report_YYYYMMDD_HHMMSS.pdf")
    print("\n" + "="*70 + "\n")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n⏳ Processing shutdown...")
        signal_handler(None, None)