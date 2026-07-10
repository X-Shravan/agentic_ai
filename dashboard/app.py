from flask import Flask, render_template, Response, jsonify
import cv2
import threading

app = Flask(__name__)

# Global system data (updated by AI system)
system_data = {
    "status": "running",
    "students": 0,
    "alerts": [],
}

camera = cv2.VideoCapture(0)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )


@app.route("/")
def index():
    return render_template(
        "index.html",
        status=system_data["status"]
    )


@app.route("/video")
def video():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/stats")
def stats():
    return jsonify(system_data)


@app.route("/alerts")
def alerts():
    return jsonify(system_data["alerts"])


# Example function to update dashboard data
def update_dashboard(students, alert_msg=None):

    system_data["students"] = students

    if alert_msg:
        system_data["alerts"].append(alert_msg)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)