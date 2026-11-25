'use client';

import { useEffect, useRef, useState, memo } from 'react';
import { FiCamera, FiRefreshCw, FiWifiOff } from 'react-icons/fi';
import { API_BASE_URL } from '../services/api';

interface WebRTCVideoProps {
  cameraId: string;
  apiUrl?: string;
  onError?: (error: string) => void;
  onConnected?: () => void;
  className?: string;
}

export const WebRTCVideo = memo(function WebRTCVideo({
  cameraId,
  apiUrl = API_BASE_URL,
  onError,
  onConnected,
  className = '',
}: WebRTCVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const frameTimerRef = useRef<number | null>(null);
  const onErrorRef = useRef(onError);
  const onConnectedRef = useRef(onConnected);
  const [status, setStatus] = useState<'waiting' | 'connecting' | 'connected' | 'reconnecting'>('waiting');
  const [fps, setFps] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const apiBaseUrl = apiUrl.replace(/\/api\/?$/, '');

  useEffect(() => {
    onErrorRef.current = onError;
    onConnectedRef.current = onConnected;
  }, [onError, onConnected]);

  useEffect(() => {
    let disposed = false;

    const cleanupPeer = () => {
      if (frameTimerRef.current) {
        window.cancelAnimationFrame(frameTimerRef.current);
        frameTimerRef.current = null;
      }
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      const video = videoRef.current;
      if (video?.srcObject) {
        const stream = video.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        video.srcObject = null;
      }
    };

    const scheduleReconnect = (message?: string) => {
      if (disposed) return;
      cleanupPeer();
      setFps(0);
      setError(message ?? null);
      setStatus((current) => (current === 'waiting' ? 'waiting' : 'reconnecting'));
      if (message) onErrorRef.current?.(message);
      if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = window.setTimeout(() => {
        void setupWebRTC(true);
      }, 3500);
    };

    const setupWebRTC = async (isRetry = false) => {
      try {
        cleanupPeer();
        setStatus(isRetry ? 'reconnecting' : 'connecting');
        setError(null);

        const pc = new RTCPeerConnection({
          iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
          ],
        });

        pcRef.current = pc;

        pc.addTransceiver('video', { direction: 'recvonly' });

        pc.onconnectionstatechange = () => {
          if (pc.connectionState === 'connected') {
            setStatus('connected');
            setError(null);
            onConnectedRef.current?.();
          } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
            scheduleReconnect(`Camera ${pc.connectionState}`);
          }
        };

        pc.oniceconnectionstatechange = () => {
          if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
            scheduleReconnect(`ICE ${pc.iceConnectionState}`);
          }
        };

        pc.ontrack = (event) => {
          if (event.track.kind === 'video' && videoRef.current) {
            const stream = event.streams[0] ?? new MediaStream([event.track]);
            videoRef.current.srcObject = stream;
            videoRef.current.play().catch((error) => {
              const errorMsg = error instanceof Error ? error.message : String(error);
              onErrorRef.current?.(errorMsg);
              setError(errorMsg);
            });

            let frameCount = 0;
            let lastTime = Date.now();

            const updateFPS = () => {
              frameCount++;
              const now = Date.now();
              if (now - lastTime >= 1000) {
                setFps(frameCount);
                frameCount = 0;
                lastTime = now;
              }
              frameTimerRef.current = window.requestAnimationFrame(updateFPS);
            };

            frameTimerRef.current = window.requestAnimationFrame(updateFPS);
          }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        await new Promise<void>((resolve) => {
          if (pc.iceGatheringState === 'complete') {
            resolve();
            return;
          }
          const handleGathering = () => {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', handleGathering);
              resolve();
            }
          };
          pc.addEventListener('icegatheringstatechange', handleGathering);
          window.setTimeout(() => {
            pc.removeEventListener('icegatheringstatechange', handleGathering);
            resolve();
          }, 5000);
        });

        const response = await fetch(`${apiBaseUrl}/api/webrtc/${cameraId}/offer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sdp: pc.localDescription?.sdp ?? offer.sdp,
            type: 'offer',
          }),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.statusText}`);
        }

        const answer = await response.json();
        await pc.setRemoteDescription(new RTCSessionDescription(answer));
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        scheduleReconnect(errorMsg);
      }
    };

    void setupWebRTC(false);

    return () => {
      disposed = true;
      if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
      cleanupPeer();
    };
  }, [cameraId, apiBaseUrl]);

  const isConnected = status === 'connected';
  const statusText = status === 'connected' ? 'Live' : status === 'reconnecting' ? 'Reconnecting...' : 'Waiting for Camera...';

  return (
    <div className={`relative min-h-[260px] overflow-hidden rounded-3xl border border-slate-700/60 bg-slate-950 ${className}`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.18),transparent_42%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.07)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.07)_1px,transparent_1px)] bg-[size:36px_36px] opacity-40" />
      <div className="relative h-full min-h-[260px]">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className={`h-full min-h-[260px] w-full object-cover transition-opacity duration-500 ${isConnected ? 'opacity-100' : 'opacity-20'}`}
        />
        {!isConnected && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-200 shadow-2xl shadow-cyan-500/10">
              {status === 'reconnecting' || status === 'connecting' ? <FiRefreshCw className="h-7 w-7 animate-spin" /> : <FiWifiOff className="h-7 w-7" />}
            </div>
            <p className="text-lg font-semibold text-white">{statusText}</p>
            <p className="mt-2 max-w-sm text-sm text-slate-400">
              {error ? error : 'The dashboard will automatically retry the existing backend WebRTC stream.'}
            </p>
          </div>
        )}
        <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full border border-white/10 bg-black/50 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-white backdrop-blur-xl">
          <span className={`h-2 w-2 rounded-full ${isConnected ? 'animate-pulse bg-emerald-400' : 'bg-amber-400'}`} />
          {statusText}
          {fps > 0 && <span className="text-slate-300">• {fps} FPS</span>}
        </div>
        <div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-xs text-slate-300 backdrop-blur-xl">
          <FiCamera className="text-cyan-300" />
          Camera ID: <span className="font-semibold text-white">{cameraId}</span>
        </div>
      </div>
    </div>
  );
});
