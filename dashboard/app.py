from flask import Flask, render_template, Response, jsonify
try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None
from backend.camera_manager import CameraManager
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global system data (updated by AI system)
system_data = {
    "status": "running",
    "students": 0,
    "alerts": [],
}

# Try to initialize camera through CameraManager, but don't fail if unavailable
camera_manager = CameraManager([{"id": "dashboard_cam", "name": "Dashboard Camera", "type": "webcam", "device_index": 0}])
camera_available = camera_manager.start_all()
if not camera_available:
    logger.warning("⚠️ Camera not available")


def generate_frames():
    """Generate frames from camera"""
    while True:
        try:
            frames = camera_manager.read_all() if camera_available else {}
            frame = frames.get("dashboard_cam")
            if frame is None:
                import numpy as np
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
            if cv2 is None:
                break
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )
        except Exception as e:
            logger.error(f"Frame generation error: {e}")
            break


@app.route("/")
def index():
    """Serve main dashboard page"""
    try:
        return render_template(
            "index.html",
            status=system_data["status"]
        )
    except Exception as e:
        logger.warning(f"Template not found: {e}")
        return f"""
        <html>
        <head><title>Exam Surveillance Dashboard</title></head>
        <body>
            <h1>Exam Surveillance Dashboard</h1>
            <p>Status: {system_data['status']}</p>
            <p><a href="/stats">View Statistics</a></p>
        </body>
        </html>
        """


@app.route("/video")
def video():
    """Stream video from camera"""
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/stats")
def stats():
    """Get system statistics"""
    return jsonify(system_data)


@app.route("/alerts")
def alerts():
    """Get system alerts"""
    return jsonify({
        "alerts": system_data["alerts"],
        "count": len(system_data["alerts"])
    })


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "dashboard",
        "camera_available": camera_available
    })


# Example function to update dashboard data
def update_dashboard(students, alert_msg=None):
    """Update dashboard with new data"""
    system_data["students"] = students

    if alert_msg:
        system_data["alerts"].append({
            "message": alert_msg,
            "timestamp": str(__import__('datetime').datetime.now())
        })


if __name__ == "__main__":
    logger.info("🚀 Starting Flask Dashboard on http://localhost:5000")
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Failed to start dashboard: {e}")