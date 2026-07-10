"""
WebRTC Streaming Server for Multi-Camera Surveillance
Uses aiortc for low-latency video streaming
Completely separate from WebSocket alert system
"""

from __future__ import annotations
import asyncio
import logging
from typing import Dict, Set
import cv2
import numpy as np
from av import VideoFrame
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaBlackhole
from fastapi import FastAPI, HTTPException, WebSocketException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    
    def put(self, frame: np.ndarray, timestamp: float) -> None:
        """Put frame - automatically drops old if full"""
        with self.condition:
            self.queue.append((frame.copy(), timestamp))
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
    
    def __init__(self, frame_buffer: FrameBuffer, fps: int = 30):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.fps = fps
        self.pts = 0
        self.time_base = None
    
    async def recv(self) -> VideoFrame:
        """
        Receive frames from buffer and encode as VP8
        Runs at specified FPS regardless of processing speed
        """
        frame_data = self.frame_buffer.get()
        
        if frame_data is None:
            # No frame available - return black frame
            frame = VideoFrame.from_ndarray(
                np.zeros((480, 640, 3), dtype=np.uint8),
                format="bgr24"
            )
        else:
            frame_array, _ = frame_data
            # Convert BGR to VideoFrame (handles color space conversion)
            frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
        
        # Set timing
        frame.pts = self.pts
        frame.time_base = "1/30"  # 30 FPS
        self.pts += 900  # Increment by 900 for 30 FPS at 27kHz clock
        
        # Get frame, sleep for frame interval to maintain FPS
        await asyncio.sleep(1.0 / self.fps)
        return frame


class WebRTCServer:
    """
    Enterprise WebRTC streaming server supporting multiple cameras
    """
    def __init__(self, config: dict):
        self.config = config
        self.frame_buffers: Dict[str, FrameBuffer] = {}  # camera_id -> FrameBuffer
        self.peer_connections: Dict[str, Set[RTCPeerConnection]] = {}  # camera_id -> Set[PCeer]
        self.lock = threading.Lock()
        
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
    
    def push_frame(self, camera_id: str, frame: np.ndarray, timestamp: float) -> None:
        """
        Push frame to buffer for a camera
        Automatically drops old frames - always streams latest
        """
        if camera_id not in self.frame_buffers:
            self.register_camera(camera_id)
        
        self.frame_buffers[camera_id].put(frame, timestamp)
    
    async def handle_offer(self, camera_id: str, offer: RTCSessionDescription) -> RTCSessionDescription:
        """
        Handle WebRTC SDP offer and return answer
        Creates peer connection and media track
        """
        if camera_id not in self.frame_buffers:
            self.register_camera(camera_id)
        
        pc = RTCPeerConnection()
        
        # Add video track from frame buffer
        frame_buffer = self.frame_buffers[camera_id]
        video_track = VideoStreamTrack(frame_buffer, self.fps)
        pc.addTrack(video_track)
        
        # Store connection
        with self.lock:
            self.peer_connections[camera_id].add(pc)
        
        @pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = pc.connectionState
            logger.info(f"🔗 Camera {camera_id} connection state: {state}")
            if state == "closed":
                with self.lock:
                    self.peer_connections[camera_id].discard(pc)
                await pc.close()
        
        # Set remote description (offer) and create answer
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return pc.localDescription
    
    def get_camera_status(self, camera_id: str) -> dict:
        """Get current status of a camera stream"""
        with self.lock:
            if camera_id not in self.frame_buffers:
                return {"status": "not_registered", "connected_peers": 0}
            
            peers = len(self.peer_connections.get(camera_id, set()))
            has_frame = not self.frame_buffers[camera_id].is_empty()
            
            return {
                "status": "streaming" if has_frame else "waiting",
                "connected_peers": peers,
                "fps": self.fps,
                "codec": self.codec,
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
            for peers in self.peer_connections.values():
                for pc in peers:
                    await pc.close()
            self.peer_connections.clear()


# Global WebRTC server instance
webrtc_server: WebRTCServer | None = None


def init_webrtc_server(config: dict) -> WebRTCServer:
    """Initialize WebRTC server"""
    global webrtc_server
    webrtc_server = WebRTCServer(config)
    return webrtc_server


def get_webrtc_server() -> WebRTCServer:
    """Get global WebRTC server instance"""
    if webrtc_server is None:
        raise RuntimeError("WebRTC server not initialized")
    return webrtc_server
