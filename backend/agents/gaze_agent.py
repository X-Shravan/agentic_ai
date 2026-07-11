"""Eye gaze agent using MediaPipe Iris signals."""

class GazeAgent:
    def analyze(self, frame, face=None):
        return {"iris_detected": False, "direction": "unknown", "fixation": 0.0}
