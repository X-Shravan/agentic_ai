"""
Integration Template for Report System with API Server
This shows exactly where and how to add report integration to api_server.py
"""

# ===================================================
# ADDITIONS TO API_SERVER.PY
# ===================================================

# ==== ADD THESE IMPORTS AT THE TOP ====
# (After existing imports)

from report_integration import (
    initialize_report_system,
    log_alert_to_report,
    generate_session_report
)

# ==== IN GLOBAL VARIABLES SECTION ====
# (After existing globals, add monitoring time tracker)

surveillance_system = None
surveillance_thread = None
monitoring_start_time = None  # ← ADD THIS

# ==== IN surveillance_loop() FUNCTION ====
# (Where alerts are currently detected)

# BEFORE your alert detection code, ADD:
global monitoring_start_time
monitoring_start_time = datetime.now()

# THEN, IN THE MAIN LOOP where you detect alerts:
# Find this section in your existing code:
#
#     for tid, dec in decisions.items():
#         if dec.should_alert:
#             # ... existing code ...
#             self.evidence.save_screenshot(frame, tid, dec.risk_score, events)

# REPLACE WITH:
#
#     for tid, dec in decisions.items():
#         if dec.should_alert:
#             # ... existing code ...
#             self.evidence.save_screenshot(frame, tid, dec.risk_score, events)
#             
#             # ← ADD THESE LINES:
#             # Log alert for report generation
#             behavior = dec.situation if hasattr(dec, 'situation') else 'Unknown'
#             log_alert_to_report(
#                 student_id=tid,
#                 behavior_type=behavior,
#                 timestamp=datetime.now().strftime("%H:%M:%S"),
#                 image_path=f"evidence/ID{tid}_{datetime.now().strftime('%H%M%S')}.jpg"
#             )

# ==== IN FINALLY BLOCK OF surveillance_loop() ====
# (At the very end when monitoring stops)

# Add before the final cleanup:
finally:
    print("🛑 Generating final report...")
    
    # Calculate monitoring time
    if monitoring_start_time:
        elapsed = datetime.now() - monitoring_start_time
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        seconds = int(elapsed.total_seconds() % 60)
        monitoring_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        monitoring_time_str = "00:00:00"
    
    # Generate and send report
    report_result = generate_session_report(
        total_students=dashboard_data.total_students,
        active_ids=len(dashboard_data.active_ids),
        total_alerts=len(dashboard_data.alerts),
        normal_students=max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
        monitoring_time=monitoring_time_str,
        send_email=True,      # Send automatically
        clear_logs=True       # Clear for next session
    )
    
    if report_result['success']:
        print(f"✅ Report generated: {report_result['report_path']}")
        if report_result['email_sent']:
            print(f"📧 Email sent to recipient")
        if report_result['logs_cleared']:
            print(f"🧹 Logs cleared for next session")
    else:
        print(f"⚠️ Report generation issue: {report_result['message']}")
    
    # Rest of existing cleanup code...
    dashboard_data.system_running = False
    # ... etc ...

# ==== IN __main__ SECTION ====
# (At startup, before starting surveillance thread)

if __name__ == '__main__':
    print("🔧 Starting AI Exam Surveillance Dashboard API Server...")
    
    # ← ADD THIS:
    # Initialize report system (will use environment variables for credentials)
    try:
        initialize_report_system()
        print("📊 Report system initialized")
    except Exception as e:
        print(f"⚠️ Report system initialization warning: {e}")
        print("   Reports can still be generated without email")
    
    # Start surveillance system in background thread
    surveillance_thread = threading.Thread(target=surveillance_loop, daemon=True)
    surveillance_thread.start()
    
    # Rest of existing code...
    print("🚀 API Server running on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)


# ===================================================
# COMPLETE MODIFIED SECTION EXAMPLE
# ===================================================

"""
Here's a complete example of the surveillance_loop with report integration:

def surveillance_loop():
    global surveillance_system, dashboard_data, monitoring_start_time
    
    print("🚀 Starting Surveillance System...")
    dashboard_data.system_status["monitoring"] = "Starting"
    dashboard_data.system_status["detection"] = "Starting"
    
    try:
        surveillance_system = ExamSurveillanceSystem(config_path="config/config.yaml", demo_mode=True)
        
        if not surveillance_system.start():
            print("❌ Failed to start surveillance system")
            dashboard_data.system_status["monitoring"] = "Error"
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
        
        # ← INITIALIZE MONITORING START TIME
        monitoring_start_time = datetime.now()
        
        frame_count = 0
        
        while True:
            results = surveillance_system.process_frame()
            
            if not results:
                time.sleep(0.01)
                continue
            
            dashboard_data.last_frame_time = datetime.now()
            dashboard_data.frame_count += 1
            
            for cam_id, data in results.items():
                tracks = data.get("tracks", [])
                scores = data.get("scores", {})
                frame = data.get("frame")
                
                dashboard_data.total_students = len(tracks)
                dashboard_data.active_ids = [t.track_id for t in tracks]
                
                current_alerts = []
                for tid, score_data in scores.items():
                    label = score_data.get("label", "Normal")
                    situation = score_data.get("situation", "Normal")
                    score = score_data.get("score", 0)
                    
                    if "Alert" in label or "Suspicious" in label:
                        alert_dict = {
                            "id": tid,
                            "type": situation,
                            "severity": "HIGH" if "Alert" in label else "MEDIUM",
                            "timestamp": datetime.now().isoformat(),
                            "score": score
                        }
                        current_alerts.append(alert_dict)
                        
                        # ← LOG ALERT FOR REPORT
                        log_alert_to_report(
                            student_id=tid,
                            behavior_type=situation,
                            timestamp=datetime.now().strftime("%H:%M:%S"),
                            image_path=f"evidence/ID{tid}_{datetime.now().strftime('%H%M%S')}.jpg"
                        )
                        
                        if situation == "Using Mobile":
                            dashboard_data.cheating_types["Using Mobile"] += 1
                        # ... etc ...
                
                dashboard_data.alerts = current_alerts[-3:]
                dashboard_data.alert_history.extend(current_alerts)
                
                dashboard_data.timestamps.append(datetime.now().isoformat())
                dashboard_data.alert_counts.append(len(current_alerts))
                
                if frame is not None:
                    _, buffer = cv2.imencode('.jpg', frame)
                    dashboard_data.current_frame = base64.b64encode(buffer).decode('utf-8')
                
                with app.app_context():
                    socketio.emit('surveillance_update', {
                        'total_students': dashboard_data.total_students,
                        'active_ids': len(dashboard_data.active_ids),
                        'total_alerts': len(current_alerts),
                        'normal_students': dashboard_data.total_students - len(current_alerts),
                        'alerts': current_alerts,
                        'cheating_types': dict(dashboard_data.cheating_types),
                        'timestamp': datetime.now().isoformat()
                    })
            
            frame_count += 1
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\\n⚠️ Surveillance loop interrupted")
    except Exception as e:
        print(f"❌ Error in surveillance loop: {e}")
        import traceback
        traceback.print_exc()
        dashboard_data.system_status["monitoring"] = "Error"
        dashboard_data.system_status["detection"] = "Error"
    finally:
        print("🛑 Generating final report...")
        
        # ← GENERATE AND SEND REPORT
        if monitoring_start_time:
            elapsed = datetime.now() - monitoring_start_time
            hours = int(elapsed.total_seconds() // 3600)
            minutes = int((elapsed.total_seconds() % 3600) // 60)
            seconds = int(elapsed.total_seconds() % 60)
            monitoring_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            monitoring_time_str = "00:00:00"
        
        report_result = generate_session_report(
            total_students=dashboard_data.total_students,
            active_ids=len(dashboard_data.active_ids),
            total_alerts=len(dashboard_data.alerts),
            normal_students=max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
            monitoring_time=monitoring_time_str,
            send_email=True,
            clear_logs=True
        )
        
        if report_result['success']:
            print(f"✅ Report: {report_result['report_path']}")
            if report_result['email_sent']:
                print(f"📧 Email sent")
        else:
            print(f"⚠️ Report issue: {report_result['message']}")
        
        # Existing cleanup
        dashboard_data.system_running = False
        dashboard_data.camera_active = False
        dashboard_data.detection_active = False
        dashboard_data.system_status["monitoring"] = "Stopped"
        dashboard_data.system_status["detection"] = "Stopped"
        dashboard_data.system_status["camera"] = "Disconnected"
        if surveillance_system:
            surveillance_system.stop()
        print("🛑 Surveillance system stopped")
"""

# ===================================================
# KEY INTEGRATION POINTS
# ===================================================

"""
1. IMPORTS (Top of file)
   from report_integration import initialize_report_system, log_alert_to_report, generate_session_report

2. INITIALIZE (In __main__ at startup)
   initialize_report_system()

3. LOG ALERTS (Inside surveillance_loop when alert detected)
   log_alert_to_report(student_id, behavior_type, timestamp, image_path)

4. GENERATE REPORT (In finally block when monitoring stops)
   generate_session_report(total_students, active_ids, total_alerts, normal_students, monitoring_time)

That's it! The system will:
- Collect real alerts during monitoring
- Generate professional PDF with evidence
- Send via email automatically
- Clear logs for next session
"""

# ===================================================
# ENVIRONMENT SETUP REQUIRED
# ===================================================

"""
Before running, set environment variables:

Windows CMD (Run as Admin):
  setx SURVEILLANCE_EMAIL "your-email@gmail.com"
  setx SURVEILLANCE_APP_PASSWORD "abcdefghijklmnop"
  setx SURVEILLANCE_RECIPIENT "recipient@gmail.com"

Windows PowerShell:
  $env:SURVEILLANCE_EMAIL = "your-email@gmail.com"
  $env:SURVEILLANCE_APP_PASSWORD = "abcdefghijklmnop"
  $env:SURVEILLANCE_RECIPIENT = "recipient@gmail.com"

Or create .env file:
  SURVEILLANCE_EMAIL=your-email@gmail.com
  SURVEILLANCE_APP_PASSWORD=abcdefghijklmnop
  SURVEILLANCE_RECIPIENT=recipient@gmail.com

Get app password from:
  https://myaccount.google.com → Security → App passwords
"""

if __name__ == "__main__":
    print("📋 This is an integration template for report_system.py")
    print("See comments above for exact changes needed in api_server.py")
