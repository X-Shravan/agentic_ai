from __future__ import annotations

import time
from collections import defaultdict, deque


class RiskScoringAgent:

    def __init__(self, config):

        # 🔥 weights
        self.weights = {
            "Alert 🚨": 90,
            "copy": 70,
            "share": 60,
            "around": 30,
            "lean": 20,
            "Suspicious": 40,
            "Normal": 0
        }

        self.score_history = defaultdict(lambda: deque(maxlen=10))
        self.time_history = defaultdict(lambda: deque(maxlen=10))

    # -------------------------------------------------
    def calculate_scores(self, detections, behavior_results, associations):

        results = {}
        current_time = time.time()

        for tid, events in behavior_results.items():

            if not events:
                continue

            event_type = events[0].event_type

            base_score = self.weights.get(event_type, 0)

            # store history
            self.score_history[tid].append(base_score)
            self.time_history[tid].append(current_time)

            # last 5 seconds
            recent_scores = [
                s for s, t in zip(self.score_history[tid], self.time_history[tid])
                if current_time - t <= 5
            ]

            avg_score = sum(recent_scores) / len(recent_scores) if recent_scores else 0
            final_score = min(100, avg_score)

            # label
            if final_score >= 80:
                label = "High Risk 🚨"
            elif final_score >= 50:
                label = "Suspicious"
            else:
                label = "Normal"

            # 🔥 IMPORTANT: keep events for compatibility
            results[tid] = {
                "score": round(final_score, 2),
                "label": label,
                "events": [event_type],   # ✅ REQUIRED
                "situation": events[0].situation if hasattr(events[0], 'situation') else event_type
            }

        return results

    # -------------------------------------------------
    def associate_detections_to_tracks(self, detections, tracks, max_distance=120):

        associations = {}
        for track in tracks:
            associations[track.track_id] = []

        return associations

    # -------------------------------------------------
    def reset(self):
        self.score_history.clear()
        self.time_history.clear()