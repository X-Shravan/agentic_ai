from flask import Flask, render_template, Response, jsonify
import cv2
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

# Try to initialize camera, but don't fail if unavailable
camera = None
try:
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        logger.warning("⚠️ Camera not available")
        camera = None
except Exception as e:
    logger.warning(f"⚠️ Could not initialize camera: {e}")
    camera = None


def generate_frames():
    """Generate frames from camera"""
    if camera is None:
        # Return a placeholder black frame if no camera
        while True:
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )
    else:
        while True:
            try:
                success, frame = camera.read()
                if not success:
                    break

                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    frame_bytes +
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
        "camera_available": camera is not None
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