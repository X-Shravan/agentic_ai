"""
Frontend Dashboard Setup Guide
Next.js + React + WebRTC streaming + WebSocket alerts
"""

# FRONTEND_SETUP.md

# Enterprise Exam Surveillance - Frontend Dashboard

## 🎨 Frontend Architecture

```
┌─────────────────────────────────────────┐
│   Vercel / Next.js Frontend             │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ Multi-Camera WebRTC Grid          │  │
│  │ ✓ Native HTML <video> elements    │  │
│  │ ✓ Browser hardware acceleration   │  │
│  │ ✓ Independent stream rendering    │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ Real-Time Alerts Panel            │  │
│  │ ✓ WebSocket connection (metadata) │  │
│  │ ✓ Severity-based styling          │  │
│  │ ✓ Sound notifications             │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ Analytics & Heatmaps              │  │
│  │ ✓ Risk scoring visualization      │  │
│  │ ✓ Behavior heatmaps               │  │
│  │ ✓ Timeline charts                 │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │ Student Seat Map                  │  │
│  │ ✓ Interactive grid                │  │
│  │ ✓ Risk indicators                 │  │
│  │ ✓ Click for details               │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         ↓ WebRTC (Video)
    Edge AI Server
         ↓ WebSocket (Alerts)
    FastAPI Backend
```

## 📦 Tech Stack

```json
{
  "framework": "Next.js 14+",
  "runtime": "React 18+",
  "styling": "Tailwind CSS",
  "ui_components": "Shadcn UI",
  "animation": "Framer Motion",
  "state_management": "Zustand",
  "data_fetching": "TanStack Query",
  "websocket": "Socket.io client",
  "webrtc": "simple-peer / aiortc.js",
  "charts": "Recharts",
  "icons": "Lucide React"
}
```

## 🚀 Quick Start

### 1. Create Next.js Project

```bash
npx create-next-app@latest surveillance-dashboard --typescript --tailwind
cd surveillance-dashboard

# Install dependencies
npm install react-query socket.io-client simple-peer recharts framer-motion zustand lucide-react @shadcn/ui
```

### 2. Environment Setup

Create `.env.local`:

```env
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_WS=ws://localhost:8000/ws
NEXT_PUBLIC_WEBRTC_URL=http://localhost:8000/api/webrtc

# Camera configuration
NEXT_PUBLIC_CAMERA_COUNT=6
NEXT_PUBLIC_DEFAULT_CAMERA=camera_1

# Features
NEXT_PUBLIC_ENABLE_ALERTS=true
NEXT_PUBLIC_ENABLE_HEATMAP=true
NEXT_PUBLIC_ENABLE_ANALYTICS=true
```

### 3. Project Structure

```
surveillance-dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home/Dashboard
│   │   └── api/
│   │       └── auth/           # Authentication APIs
│   ├── components/
│   │   ├── Camera/
│   │   │   ├── WebRTCViewer.tsx     # WebRTC streaming
│   │   │   ├── CameraGrid.tsx       # Multi-camera grid
│   │   │   └── CameraControls.tsx   # Camera selection
│   │   ├── Alerts/
│   │   │   ├── AlertPanel.tsx       # Real-time alerts
│   │   │   ├── AlertCard.tsx        # Individual alert
│   │   │   └── AlertHistory.tsx     # Alert history
│   │   ├── Analytics/
│   │   │   ├── RiskChart.tsx        # Risk score timeline
│   │   │   ├── HeatmapView.tsx      # Suspicious activity heatmap
│   │   │   └── StatsPanel.tsx       # Key metrics
│   │   ├── StudentMap/
│   │   │   ├── SeatMap.tsx          # Interactive seat map
│   │   │   ├── StudentCard.tsx      # Student details
│   │   │   └── RiskIndicator.tsx    # Risk status
│   │   └── Common/
│   │       ├── Navbar.tsx           # Navigation
│   │       ├── Sidebar.tsx          # Side navigation
│   │       └── LoadingSpinner.tsx
│   ├── hooks/
│   │   ├── useWebRTC.ts             # WebRTC streaming logic
│   │   ├── useWebSocket.ts          # Alert WebSocket
│   │   ├── useAlerts.ts             # Alert management
│   │   └── useCamera.ts             # Camera management
│   ├── store/
│   │   ├── alertStore.ts            # Alert state (Zustand)
│   │   ├── cameraStore.ts           # Camera state
│   │   └── uiStore.ts               # UI state
│   ├── lib/
│   │   ├── api.ts                   # API client
│   │   ├── webrtc.ts                # WebRTC utilities
│   │   ├── websocket.ts             # WebSocket utilities
│   │   └── constants.ts             # Constants
│   └── styles/
│       └── globals.css              # Global styles
├── public/
│   ├── sounds/
│   │   ├── alert.mp3                # Alert sound
│   │   └── warning.mp3
│   └── images/
├── .env.local
├── tsconfig.json
├── next.config.js
├── tailwind.config.js
└── package.json
```

## 📺 WebRTC Streaming Implementation

### WebRTCViewer Component

```typescript
// components/Camera/WebRTCViewer.tsx

import { useEffect, useRef, useState } from 'react';
import SimplePeer from 'simple-peer';

interface WebRTCViewerProps {
  cameraId: string;
  apiUrl: string;
}

export function WebRTCViewer({ cameraId, apiUrl }: WebRTCViewerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const peerRef = useRef<SimplePeer.Instance | null>(null);

  useEffect(() => {
    const connectWebRTC = async () => {
      try {
        // 1. Create peer connection
        const peer = new SimplePeer({
          initiator: true,
          trickle: false,
          stream: undefined,
        });

        peerRef.current = peer;

        // 2. On signal (SDP offer)
        peer.on('signal', async (data) => {
          const response = await fetch(
            `${apiUrl}/api/webrtc/${cameraId}/offer`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                sdp: data.sdp,
                type: 'offer',
              }),
            }
          );

          const answer = await response.json();
          peer.signal(answer); // Send SDP answer
        });

        // 3. On stream (video from server)
        peer.on('stream', (stream) => {
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            videoRef.current.play();
          }
        });

        // 4. Error handling
        peer.on('error', (err) => {
          console.error(`WebRTC error for ${cameraId}:`, err);
        });

      } catch (error) {
        console.error('Failed to connect WebRTC:', error);
      }
    };

    connectWebRTC();

    return () => {
      if (peerRef.current) {
        peerRef.current.destroy();
      }
    };
  }, [cameraId, apiUrl]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      style={{
        width: '100%',
        height: '100%',
        background: '#000',
      }}
    />
  );
}
```

### CameraGrid Component

```typescript
// components/Camera/CameraGrid.tsx

import { WebRTCViewer } from './WebRTCViewer';
import { useStore } from '@/store';
import { useState } from 'react';

export function CameraGrid() {
  const { cameras, selectedCamera } = useStore();
  const [fullscreenCameraId, setFullscreenCameraId] = useState<string | null>(null);

  if (fullscreenCameraId) {
    return (
      <div className="w-full h-screen bg-black">
        <button
          onClick={() => setFullscreenCameraId(null)}
          className="absolute top-4 right-4 z-10 bg-red-500 text-white px-4 py-2 rounded"
        >
          Exit Fullscreen
        </button>
        <WebRTCViewer cameraId={fullscreenCameraId} apiUrl={process.env.NEXT_PUBLIC_WEBRTC_URL!} />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 h-full bg-gray-900 p-4">
      {cameras.map((camera) => (
        <div
          key={camera.id}
          className="relative bg-black rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-blue-500 transition"
          onClick={() => setFullscreenCameraId(camera.id)}
        >
          <WebRTCViewer cameraId={camera.id} apiUrl={process.env.NEXT_PUBLIC_WEBRTC_URL!} />
          
          {/* Camera label */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-2">
            <p className="text-white text-sm font-semibold">{camera.name}</p>
            <p className="text-gray-400 text-xs">
              {camera.students_tracked} students | {camera.fps} FPS
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

## 🔔 WebSocket Alerts Implementation

### useWebSocket Hook

```typescript
// hooks/useWebSocket.ts

import { useEffect, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useStore } from '@/store';

export function useWebSocket(userId: string) {
  const { addAlert, updateStatus } = useStore();

  useEffect(() => {
    const socket: Socket = io(process.env.NEXT_PUBLIC_API_WS, {
      query: { user_id: userId },
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    // Connect
    socket.on('connect', () => {
      console.log('✅ Connected to alert server');
      updateStatus('connected');
    });

    // Receive alert
    socket.on('alert', (data) => {
      console.log('🚨 Alert received:', data);
      addAlert(data);
      
      // Play notification sound
      const audio = new Audio('/sounds/alert.mp3');
      audio.play().catch(e => console.log('Audio play failed:', e));
    });

    // Receive status update
    socket.on('status', (data) => {
      console.log('📊 Status update:', data);
      updateStatus(data);
    });

    // Subscribe to camera
    socket.emit('subscribe', { camera_id: 'camera_1' });

    // Disconnect
    socket.on('disconnect', () => {
      console.log('❌ Disconnected from alert server');
      updateStatus('disconnected');
    });

    return () => {
      socket.disconnect();
    };
  }, [userId, addAlert, updateStatus]);
}
```

### AlertPanel Component

```typescript
// components/Alerts/AlertPanel.tsx

import { useStore } from '@/store';
import { AlertCard } from './AlertCard';
import { motion, AnimatePresence } from 'framer-motion';

export function AlertPanel() {
  const { alerts, recentAlerts } = useStore();

  return (
    <div className="bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-red-600 text-white p-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">Real-Time Alerts</h2>
        <span className="bg-white text-red-600 px-3 py-1 rounded-full font-bold">
          {alerts.length}
        </span>
      </div>

      {/* Alert list */}
      <div className="max-h-96 overflow-y-auto">
        <AnimatePresence>
          {alerts.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No alerts
            </div>
          ) : (
            alerts.map((alert) => (
              <motion.div
                key={alert.alert_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.3 }}
              >
                <AlertCard alert={alert} />
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
```

## 📊 Analytics Implementation

### RiskChart Component

```typescript
// components/Analytics/RiskChart.tsx

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';

export function RiskChart({ studentId }: { studentId: string }) {
  const { data: chartData } = useQuery({
    queryKey: ['risk-chart', studentId],
    queryFn: async () => {
      const res = await fetch(`/api/analytics/student/${studentId}`);
      return res.json();
    },
    refetchInterval: 5000, // Update every 5 seconds
  });

  return (
    <LineChart width={600} height={300} data={chartData}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="time" />
      <YAxis domain={[0, 100]} />
      <Tooltip />
      <Legend />
      <Line type="monotone" dataKey="risk_score" stroke="#ef4444" name="Risk Score" />
      <Line type="monotone" dataKey="confidence" stroke="#3b82f6" name="Confidence" />
    </LineChart>
  );
}
```

## 📝 Deployment to Vercel

```bash
# 1. Push to GitHub
git add .
git commit -m "Add surveillance dashboard"
git push origin main

# 2. Deploy to Vercel
vercel deploy

# 3. Set environment variables in Vercel dashboard
# - NEXT_PUBLIC_API_URL
# - NEXT_PUBLIC_API_WS
# - NEXT_PUBLIC_WEBRTC_URL

# 4. Access dashboard
open https://your-app.vercel.app
```

## 🎯 Key Features Implementation

### ✅ Multi-Camera WebRTC Grid
- Native `<video>` elements
- Browser GPU acceleration
- No React re-renders
- Independent stream management
- Fullscreen capability

### ✅ Real-Time Alerts
- WebSocket-only (NO video frames)
- Sound notifications
- Severity-based styling
- Auto-dismiss
- Alert history

### ✅ Analytics Dashboard
- Risk score timeline
- Behavior heatmaps
- Student ranking
- Alert trends

### ✅ Student Seat Map
- Interactive grid
- Risk indicators
- Click for details
- Real-time updates

## 🔒 Security

```typescript
// Disable right-click on video
<video
  onContextMenu={(e) => e.preventDefault()}
  {...props}
/>

// Prevent video download
<video
  controlsList="nodownload"
  {...props}
/>
```

## 📱 Responsive Design

```typescript
// Mobile-first Tailwind breakpoints
<div className="grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
```

## ✨ Performance Optimization

```typescript
// Code splitting
const AlertPanel = dynamic(() => import('@/components/Alerts/AlertPanel'), {
  loading: () => <div>Loading...</div>,
});

// Image optimization
import Image from 'next/image';

// Font optimization
import { Inter } from 'next/font/google';
```

---

**Version**: 1.0.0  
**Framework**: Next.js 14+  
**Last Updated**: January 2024
