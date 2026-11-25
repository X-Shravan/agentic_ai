from __future__ import annotations

import time
from collections import deque
from typing import Deque, Tuple

from .camera_registry import CameraMetrics


class CameraHealthMonitor:
    def __init__(self, window_size: int = 60):
        self.timestamps: Deque[float] = deque(maxlen=window_size)
        self.metrics = CameraMetrics()

    def record_frame(self, resolution: Tuple[int, int], captured_at: float | None = None) -> CameraMetrics:
        now = time.time()
        captured_at = captured_at or now
        self.timestamps.append(now)
        self.metrics.frames_read += 1
        self.metrics.resolution = resolution
        self.metrics.last_frame_timestamp = now
        self.metrics.latency_ms = max(0.0, (now - captured_at) * 1000)
        if len(self.timestamps) >= 2:
            duration = max(0.001, self.timestamps[-1] - self.timestamps[0])
            self.metrics.fps = (len(self.timestamps) - 1) / duration
            self.metrics.frame_delay_ms = 1000.0 / max(0.001, self.metrics.fps)
        total = self.metrics.frames_read + self.metrics.read_failures
        if total:
            self.metrics.packet_loss_pct = (self.metrics.read_failures / total) * 100
        return self.metrics

    def record_failure(self) -> CameraMetrics:
        self.metrics.read_failures += 1
        total = self.metrics.frames_read + self.metrics.read_failures
        if total:
            self.metrics.packet_loss_pct = (self.metrics.read_failures / total) * 100
        return self.metrics

    def record_drop(self) -> CameraMetrics:
        self.metrics.dropped_frames += 1
        return self.metrics
