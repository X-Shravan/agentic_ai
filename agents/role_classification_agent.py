from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

import statistics


# -------------------------------------------------
# Role Types
# -------------------------------------------------
class PersonRole(Enum):
    STUDENT = "student"
    INVIGILATOR = "invigilator"


# -------------------------------------------------
# Role Classification Result
# -------------------------------------------------
@dataclass
class RoleClassification:
    track_id: int
    role: PersonRole
    confidence: float
    mobility_score: float


# -------------------------------------------------
# Role Classification Agent
# -------------------------------------------------
class RoleClassificationAgent:

    def __init__(self, config):

        rc = config.get("role_classification", {})

        # 🔥 Adjusted for exam hall
        self.mobility_threshold = rc.get("mobility_threshold", 30)
        self.invigilator_min_mobility = rc.get("invigilator_min_mobility", 120)

        self.history_size = rc.get("history_size", 15)

        self.classifications: Dict[int, RoleClassification] = {}

        self.role_history = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )

    # -------------------------------------------------
    # Classify Tracks
    # -------------------------------------------------
    def classify(self, tracks: List[object]) -> Dict[int, RoleClassification]:

        output = {}

        for track in tracks:

            mobility = self._calculate_mobility(track)

            # -----------------------------
            # 🔥 Improved Logic
            # -----------------------------
            if mobility > self.invigilator_min_mobility:
                role = PersonRole.INVIGILATOR
                confidence = 0.9

            else:
                # Default = student (IMPORTANT)
                role = PersonRole.STUDENT

                if mobility < self.mobility_threshold:
                    confidence = 0.9
                else:
                    confidence = 0.7

            # Save history
            self.role_history[track.track_id].append(role)

            # Stabilize role
            role = self._stabilize_role(track.track_id)

            classification = RoleClassification(
                track.track_id,
                role,
                confidence,
                mobility,
            )

            output[track.track_id] = classification
            self.classifications[track.track_id] = classification

        return output

    # -------------------------------------------------
    # Mobility Calculation
    # -------------------------------------------------
    def _calculate_mobility(self, track) -> float:

        if len(track.history) < 3:
            return 0.0

        distances = []

        for i in range(1, len(track.history)):

            x1, y1 = track.history[i - 1]
            x2, y2 = track.history[i]

            dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            distances.append(dist)

        if not distances:
            return 0.0

        return float(statistics.median(distances))

    # -------------------------------------------------
    # Role Stabilization
    # -------------------------------------------------
    def _stabilize_role(self, track_id):

        history = list(self.role_history[track_id])

        if not history:
            return PersonRole.STUDENT

        student_count = history.count(PersonRole.STUDENT)
        invigilator_count = history.count(PersonRole.INVIGILATOR)

        if invigilator_count > student_count:
            return PersonRole.INVIGILATOR

        return PersonRole.STUDENT

    # -------------------------------------------------
    def is_student(self, track_id: int) -> bool:

        entry = self.classifications.get(track_id)

        return bool(entry and entry.role == PersonRole.STUDENT)

    # -------------------------------------------------
    def get_statistics(self):

        students = sum(
            1 for c in self.classifications.values()
            if c.role == PersonRole.STUDENT
        )

        invigilators = sum(
            1 for c in self.classifications.values()
            if c.role == PersonRole.INVIGILATOR
        )

        return {
            "students": students,
            "invigilators": invigilators,
            "total_classified": len(self.classifications),
        }

    # -------------------------------------------------
    def reset(self):

        self.classifications.clear()
        self.role_history.clear()