"""
WebRTC Streaming Server for Multi-Camera Surveillance
Uses aiortc for low-latency video streaming
Completely separate from WebSocket alert system
"""

from __future__ import annotations
import asyncio
import logging
from fractions import Fraction
from typing import Dict, Set
import numpy as np
from av import VideoFrame
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import threading
from collections import deque
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FrameBuffer:
    """
    Efficient frame buffer that always holds the LATEST frame only.
    Prevents backlog of old frames - always processes newest.
    """
    def __init__(self, maxsize: int = 1):
        self.queue = deque(maxlen=maxsize)
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.last_frame_timestamp: float | None = None
        self.frames_received = 0

    def put(self, frame: np.ndarray, timestamp: float) -> None:
        """Put frame - automatically drops old if full"""
        with self.condition:
            self.queue.append((frame.copy(), timestamp))
            self.last_frame_timestamp = timestamp
            self.frames_received += 1
            self.condition.notify()

    def get(self, timeout: float = 0.1) -> tuple[np.ndarray, float] | None:
        """Get latest frame without blocking"""
        with self.condition:
            if self.queue:
                return self.queue[-1]
            return None

    def is_empty(self) -> bool:
        with self.lock:
            return len(self.queue) == 0


class VideoStreamTrack(MediaStreamTrack):
    """
    WebRTC media stream track that reads from frame buffer
    Encodes to VP8 for efficient streaming
    """
    kind = "video"

    def __init__(self, frame_buffer: FrameBuffer, fps: int = 30, camera_id: str = "unknown"):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.fps = fps
        self.camera_id = camera_id
        self.pts = 0
        self.time_base = Fraction(1, max(1, fps))
        self.frame_count = 0
        self._next_timestamp = None
        logger.info(f"🎥 VideoStreamTrack created for {camera_id} @ {fps} FPS")

    async def recv(self) -> VideoFrame:
        """
        Receive frames from buffer and encode as VP8
        Runs at specified FPS regardless of processing speed
        """
        # Precise pacing to prevent drift and event-loop lag
        now = time.time()
        if self._next_timestamp is None:
            self._next_timestamp = now
        else:
            self._next_timestamp += 1.0 / self.fps

        if now > self._next_timestamp + 0.1:
            self._next_timestamp = now

        sleep_dur = self._next_timestamp - now
        if sleep_dur > 0:
            await asyncio.sleep(sleep_dur)

        self.frame_count += 1
        frame_data = self.frame_buffer.get()

        if frame_data is None:
            # No frame available - return black frame
            frame = VideoFrame.from_ndarray(
                np.zeros((480, 640, 3), dtype=np.uint8),
                format="bgr24"
            )
            frame = frame.reformat(format="yuv420p")
            logger.debug(f"📭 No frame available for {self.camera_id} (frame #{self.frame_count})")
        else:
            frame_array, frame_ts = frame_data
            # Convert BGR to YUV420P VideoFrame asynchronously inside executor
            loop = asyncio.get_event_loop()
            frame = await loop.run_in_executor(
                None,
                lambda: VideoFrame.from_ndarray(frame_array, format="bgr24").reformat(format="yuv420p")
            )
            logger.debug(f"📹 Frame {self.frame_count} sent for {self.camera_id} (shape: {frame_array.shape})")

        # Set timing
        frame.pts = self.pts
        frame.time_base = self.time_base
        self.pts += 1

        return frame



class WebRTCServer:
    """
    Enterprise WebRTC streaming server supporting multiple cameras
    """
    def __init__(self, config: dict):
        self.config = config
        self.frame_buffers: Dict[str, FrameBuffer] = {}  # camera_id -> FrameBuffer
        self.peer_connections: Dict[str, Set[RTCPeerConnection]] = {}  # camera_id -> Set[PCeer]
        self.lock = threading.RLock()
        self.started_at = time.time()

        # Video encoding params
        self.codec = "vp8"  # VP8 for better compression than H.264
        self.bitrate = config.get("webrtc", {}).get("bitrate", 2500000)  # 2.5 Mbps default
        self.fps = config.get("webrtc", {}).get("fps", 30)

        logger.info(f"🎬 WebRTC Server initialized | Codec: {self.codec} | FPS: {self.fps}")

    def register_camera(self, camera_id: str) -> None:
        """Register a new camera for streaming"""
        with self.lock:
            if camera_id not in self.frame_buffers:
                self.frame_buffers[camera_id] = FrameBuffer(maxsize=1)
                self.peer_connections[camera_id] = set()
                logger.info(f"📹 Camera registered: {camera_id}")

    async def unregister_camera(self, camera_id: str) -> bool:
        """Remove a camera stream and close only its connected peers."""
        with self.lock:
            existed = camera_id in self.frame_buffers or camera_id in self.peer_connections
            peers = list(self.peer_connections.pop(camera_id, set()))
            self.frame_buffers.pop(camera_id, None)
        await asyncio.gather(*(pc.close() for pc in peers), return_exceptions=True)
        return existed

    def push_frame(self, camera_id: str, frame: np.ndarray, timestamp: float) -> None:
        """
        Push frame to buffer for a camera
        Automatically drops old frames - always streams latest
        """
        if camera_id not in self.frame_buffers:
            self.register_camera(camera_id)

        self.frame_buffers[camera_id].put(frame, timestamp)
        logger.debug(f"📊 Frame buffer updated for {camera_id}: shape={frame.shape} @ {timestamp:.2f}")

    async def handle_offer(self, camera_id: str, offer: RTCSessionDescription) -> RTCSessionDescription:
        """
        Handle WebRTC SDP offer and return answer
        Creates peer connection and media track
        """
        if camera_id not in self.frame_buffers:
            self.register_camera(camera_id)

        logger.info(f"🤝 Handling WebRTC offer for camera {camera_id}")

        pc = RTCPeerConnection()
        logger.info(f"✅ RTCPeerConnection created for {camera_id}")

        # Add video track from frame buffer (route to active camera if requested camera has no frames)
        source_camera_id = camera_id
        with self.lock:
            if source_camera_id not in self.frame_buffers or self.frame_buffers[source_camera_id].is_empty():
                for alt_id, alt_buf in self.frame_buffers.items():
                    if not alt_buf.is_empty():
                        logger.info(f"🔄 WebRTC routing camera {camera_id} to active stream {alt_id}")
                        source_camera_id = alt_id
                        break
        frame_buffer = self.frame_buffers[source_camera_id]
        video_track = VideoStreamTrack(frame_buffer, self.fps, source_camera_id)
        pc.addTrack(video_track)
        logger.info(f"🎬 VideoStreamTrack added for {source_camera_id}")

        # Store connection
        with self.lock:
            self.peer_connections[camera_id].add(pc)

        async def remove_peer(close: bool = True) -> None:
            with self.lock:
                peers = self.peer_connections.get(camera_id)
                if peers is not None:
                    peers.discard(pc)
            if close and pc.connectionState != "closed":
                await pc.close()

        @pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = pc.connectionState
            logger.info(f"🔗 Camera {camera_id} connection state changed: {state}")
            if state == "connected":
                logger.info(f"✅ Camera {camera_id} peer connected - streaming active!")
            elif state in {"failed", "closed"}:
                logger.warning(f"❌ Camera {camera_id} peer {state}")
                await remove_peer(close=state != "closed")

        @pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            logger.debug(f"❄️ ICE candidate for {camera_id}: {candidate}")

        try:
            # setLocalDescription gathers ICE candidates for the returned SDP.
            await pc.setRemoteDescription(offer)
            logger.debug(f"📝 Remote description set for {camera_id}")

            answer = await pc.createAnswer()
            logger.debug(f"💬 Answer created for {camera_id}")

            await pc.setLocalDescription(answer)
            logger.info(f"📡 Local description set for {camera_id} - answer ready")
            return pc.localDescription
        except Exception:
            await remove_peer()
            raise

    def get_camera_status(self, camera_id: str) -> dict:
        """Get current status of a camera stream"""
        with self.lock:
            if camera_id not in self.frame_buffers:
                return {"status": "not_registered", "connected_peers": 0}

            peers = len(self.peer_connections.get(camera_id, set()))
            buffer = self.frame_buffers[camera_id]
            has_frame = not buffer.is_empty()

            return {
                "status": "streaming" if has_frame else "waiting",
                "connected_peers": peers,
                "fps": self.fps,
                "codec": self.codec,
                "last_frame_time": buffer.last_frame_timestamp,
                "frames_received": buffer.frames_received,
            }

    def get_all_cameras_status(self) -> dict:
        """Get status of all registered cameras"""
        with self.lock:
            return {
                cam_id: self.get_camera_status(cam_id)
                for cam_id in self.frame_buffers.keys()
            }

    async def cleanup(self) -> None:
        """Close all connections gracefully"""
        with self.lock:
            peers = [pc for camera_peers in self.peer_connections.values() for pc in camera_peers]
            self.peer_connections.clear()
            self.frame_buffers.clear()
        await asyncio.gather(*(pc.close() for pc in peers), return_exceptions=True)

    def health(self) -> dict:
        with self.lock:
            return {
                "status": "running",
                "registered_cameras": len(self.frame_buffers),
                "connected_peers": sum(len(peers) for peers in self.peer_connections.values()),
                "uptime_seconds": round(time.time() - self.started_at, 2),
            }


# Global WebRTC server instance
webrtc_server: WebRTCServer | None = None


def init_webrtc_server(config: dict) -> WebRTCServer:
    """Initialize WebRTC server"""
    global webrtc_server
    if webrtc_server is None:
        webrtc_server = WebRTCServer(config)
    return webrtc_server


def get_webrtc_server() -> WebRTCServer:
    """Get global WebRTC server instance"""
    if webrtc_server is None:
        raise RuntimeError("WebRTC server not initialized")
    return webrtc_server


def is_webrtc_server_initialized() -> bool:
    return webrtc_server is not None
