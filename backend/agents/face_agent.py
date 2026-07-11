"""Face analysis agent using MediaPipe Face Mesh signals."""

class FaceAnalysisAgent:
    def analyze(self, frame, track=None):
        return {"face_detected": False, "yaw": None, "pitch": None, "roll": None}
