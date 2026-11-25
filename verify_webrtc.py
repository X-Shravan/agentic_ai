#!/usr/bin/env python3
"""
WebRTC Pipeline Verification Script
Tests each stage of the camera → WebRTC → Browser pipeline
Run this after starting the backend to verify everything is connected
"""

import asyncio
import sys
import json
from datetime import datetime
import httpx

API_URL = "http://localhost:8000"
COLORS = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "RESET": "\033[0m",
}


def log(status, message, details=""):
    """Print colored log message"""
    if status == "✅":
        color = COLORS["GREEN"]
    elif status == "❌":
        color = COLORS["RED"]
    elif status == "⚠️":
        color = COLORS["YELLOW"]
    elif status == "ℹ️":
        color = COLORS["BLUE"]
    else:
        color = COLORS["RESET"]

    print(f"{color}{status} {message}{COLORS['RESET']}")
    if details:
        print(f"  {details}")


async def check_backend_running():
    """Check if backend is running"""
    log("ℹ️", "Checking if backend is running...", f"URL: {API_URL}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/cameras", timeout=5.0)
            if response.status_code == 200:
                log("✅", "Backend is running and responding")
                return True
            else:
                log("❌", f"Backend returned status {response.status_code}")
                return False
    except Exception as e:
        log("❌", "Backend is not running or not reachable", str(e))
        return False


async def check_cameras():
    """Check if cameras are detected"""
    log("ℹ️", "Checking for available cameras...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/cameras/discover", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                cameras = data.get("detected_cameras", [])
                if cameras:
                    log("✅", f"Found {len(cameras)} camera(s)")
                    for cam in cameras:
                        print(f"  - {cam.get('name', 'Unknown')}: {cam.get('camera_id')}")
                    return True, cameras
                else:
                    log("⚠️", "No cameras detected", "Check camera connections")
                    return True, []
            else:
                log("❌", f"Camera discovery failed: {response.status_code}")
                return False, []
    except Exception as e:
        log("❌", "Failed to discover cameras", str(e))
        return False, []


async def check_camera_status():
    """Check status of connected cameras"""
    log("ℹ️", "Checking camera connection status...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/cameras/status", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                statuses = data.get("status", {})

                connected = 0
                for cam_id, status in statuses.items():
                    if status.get("online"):
                        log("✅", f"Camera {cam_id} is ONLINE", f"State: {status.get('state')}")
                        connected += 1
                    else:
                        log("❌", f"Camera {cam_id} is OFFLINE", f"State: {status.get('state')}")

                if connected > 0:
                    log("✅", f"{connected} camera(s) connected and ready")
                    return True
                else:
                    log("⚠️", "No cameras currently connected", "Try POST /cameras/auto-connect")
                    return False
            else:
                log("❌", f"Status check failed: {response.status_code}")
                return False
    except Exception as e:
        log("❌", "Failed to check camera status", str(e))
        return False


async def check_webrtc_server():
    """Check if WebRTC server is initialized"""
    log("ℹ️", "Checking WebRTC server status...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/webrtc/cameras/status", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                cameras = data.get("cameras", {})

                if cameras:
                    log("✅", f"WebRTC server is running with {len(cameras)} camera(s) registered")
                    for cam_id, status in cameras.items():
                        peers = status.get("connected_peers", 0)
                        fps = status.get("fps", "?")
                        print(f"  - {cam_id}: {peers} peers, {fps} FPS")
                    return True
                else:
                    log("⚠️", "WebRTC server has no cameras registered", "Cameras may not be connected to WebRTC")
                    return False
            else:
                log("❌", f"WebRTC check failed: {response.status_code}")
                return False
    except Exception as e:
        log("❌", "Failed to check WebRTC server", str(e))
        return False


async def test_frame_push(camera_id):
    """Test if frames can be pushed to WebRTC"""
    log("ℹ️", f"Testing frame push for {camera_id}...", "Checking if WebRTC buffer receives frames")

    try:
        import cv2
        import base64
        import numpy as np

        # Generate test frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        test_frame[:, :] = (0, 255, 0)  # Green frame

        # Encode to base64
        _, buffer = cv2.imencode(".jpg", test_frame)
        frame_base64 = base64.b64encode(buffer).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/api/detection/push-frame",
                json={
                    "camera_id": camera_id,
                    "frame_base64": frame_base64,
                    "timestamp": datetime.now().isoformat(),
                },
                timeout=5.0,
            )

            if response.status_code == 200:
                log("✅", f"Frame push successful for {camera_id}")
                return True
            else:
                log("❌", f"Frame push failed: {response.status_code}", response.text)
                return False
    except ImportError:
        log("⚠️", "OpenCV not available, skipping frame push test")
        return None
    except Exception as e:
        log("❌", "Frame push test failed", str(e))
        return False


async def check_cors():
    """Check if CORS is enabled"""
    log("ℹ️", "Checking CORS headers...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.options(
                f"{API_URL}/api/webrtc/cameras/status",
                headers={"Origin": "http://localhost:3000"},
            )

            cors_header = response.headers.get("access-control-allow-origin")
            if cors_header:
                log("✅", "CORS is enabled", f"Allow-Origin: {cors_header}")
                return True
            else:
                log("⚠️", "CORS header not present", "May cause browser issues")
                return False
    except Exception as e:
        log("⚠️", "Could not check CORS", str(e))
        return False


async def run_verification():
    """Run complete verification suite"""
    print(f"\n{'='*60}")
    print("🔍 WebRTC Pipeline Verification")
    print(f"{'='*60}\n")

    results = {}

    # Stage 1: Backend
    print(f"{COLORS['BLUE']}Stage 1: Backend{COLORS['RESET']}")
    print("-" * 40)
    results["backend"] = await check_backend_running()
    if not results["backend"]:
        log("❌", "Cannot proceed - backend is not running")
        return results
    print()

    # Stage 2: Cameras
    print(f"{COLORS['BLUE']}Stage 2: Cameras{COLORS['RESET']}")
    print("-" * 40)
    results["discovery"], cameras = await check_cameras()
    results["connection"] = await check_camera_status()
    print()

    # Stage 3: WebRTC Server
    print(f"{COLORS['BLUE']}Stage 3: WebRTC Server{COLORS['RESET']}")
    print("-" * 40)
    results["webrtc"] = await check_webrtc_server()
    print()

    # Stage 4: Frame Push
    if cameras and results["connection"]:
        print(f"{COLORS['BLUE']}Stage 4: Frame Pipeline{COLORS['RESET']}")
        print("-" * 40)
        # Test first camera
        camera_id = cameras[0].get("camera_id", "webcam_0")
        result = await test_frame_push(camera_id)
        results["frame_push"] = result if result is not None else "skipped"
        print()

    # Stage 5: CORS
    print(f"{COLORS['BLUE']}Stage 5: Browser Access{COLORS['RESET']}")
    print("-" * 40)
    results["cors"] = await check_cors()
    print()

    # Summary
    print(f"{COLORS['BLUE']}Summary{COLORS['RESET']}")
    print("=" * 40)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v == "skipped")

    log("ℹ️", f"Passed: {passed} | Failed: {failed} | Skipped: {skipped}")

    if failed == 0 and passed > 0:
        log("✅", "All checks passed! Camera pipeline is ready.", "Next: Open browser and check http://localhost:3000/dashboard")
    else:
        log("⚠️", f"Some checks failed. See above for details.", "Check the logs to identify issues.")

    return results


if __name__ == "__main__":
    try:
        asyncio.run(run_verification())
    except KeyboardInterrupt:
        print("\n\n❌ Verification interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
