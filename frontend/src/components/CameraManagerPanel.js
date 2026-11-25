import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Camera, RefreshCw, RotateCcw, Power, PowerOff, Activity } from 'lucide-react';
import { API_URL } from '../config';

function statusColor(status) {
  switch ((status || '').toLowerCase()) {
    case 'online':
      return 'text-green-400 bg-green-500/10 border-green-500/30';
    case 'reconnecting':
    case 'connecting':
      return 'text-amber-300 bg-amber-500/10 border-amber-500/30';
    case 'error':
      return 'text-red-300 bg-red-500/10 border-red-500/30';
    default:
      return 'text-gray-300 bg-gray-500/10 border-gray-500/30';
  }
}

function CameraManagerPanel() {
  const [cameras, setCameras] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const loadStatus = async () => {
    setLoading(true);
    try {
      const [listResponse, statusResponse] = await Promise.all([
        fetch(`${API_URL}/cameras`),
        fetch(`${API_URL}/cameras/status`),
      ]);
      if (listResponse.ok) {
        setCameras(await listResponse.json());
      }
      if (statusResponse.ok) {
        setSummary(await statusResponse.json());
      }
      setMessage('Camera status refreshed');
    } catch (error) {
      setMessage('Camera manager API is not reachable yet');
    } finally {
      setLoading(false);
    }
  };

  const callCameraAction = async (cameraId, action) => {
    try {
      const response = await fetch(`${API_URL}/cameras/${cameraId}/${action}`, { method: 'POST' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `${action} failed`);
      }
      setMessage(`${action} requested for ${cameraId}`);
      await loadStatus();
    } catch (error) {
      setMessage(error.message || `${action} failed`);
    }
  };

  const autoConnect = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/cameras/auto-connect`, { method: 'POST' });
      const payload = await response.json();
      setMessage(payload.connected ? `Connected ${payload.primary_camera_id}` : 'No camera could be connected');
      await loadStatus();
    } catch (error) {
      setMessage('Auto-connect failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center space-x-2">
          <Camera className="text-neon-blue" />
          <span>Camera Manager</span>
        </h2>
        <div className="flex gap-2">
          <button onClick={autoConnect} className="px-3 py-2 rounded-lg bg-neon-blue/20 border border-neon-blue/40 text-neon-blue text-sm flex items-center gap-2">
            <Power size={14} /> Auto Connect
          </button>
          <button onClick={loadStatus} className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm flex items-center gap-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-3 mb-4 text-sm">
          <div className="bg-gray-900/70 border border-gray-800 rounded-lg p-3"><p className="text-gray-400">Detected</p><p className="text-lg font-bold">{summary.total_detected || 0}</p></div>
          <div className="bg-gray-900/70 border border-gray-800 rounded-lg p-3"><p className="text-gray-400">Connected</p><p className="text-lg font-bold">{summary.total_connected || 0}</p></div>
          <div className="bg-gray-900/70 border border-gray-800 rounded-lg p-3"><p className="text-gray-400">Online</p><p className="text-lg font-bold">{summary.online || 0}</p></div>
        </div>
      )}

      {message && <div className="mb-3 text-xs text-gray-300 bg-gray-900/60 border border-gray-800 rounded-lg px-3 py-2">{message}</div>}

      <div className="space-y-3 max-h-96 overflow-auto">
        {cameras.length === 0 ? (
          <div className="text-sm text-gray-400">No cameras detected yet. Use Auto Connect or update camera/camera_config.yaml.</div>
        ) : cameras.map((camera) => (
          <div key={camera.camera_id} className="bg-gray-900/70 border border-gray-800 rounded-xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-white">{camera.name || camera.camera_id}</p>
                <p className="text-xs text-gray-400">{camera.type} ? {camera.source}</p>
                {camera.last_error && <p className="text-xs text-red-300 mt-1">{camera.last_error}</p>}
              </div>
              <span className={`text-xs px-2 py-1 rounded-full border ${statusColor(camera.status)}`}>{camera.status || 'offline'}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-xs text-gray-300">
              <span className="flex items-center gap-1"><Activity size={12} /> FPS {camera.fps || 0}</span>
              <span>Resolution {(camera.resolution || []).join('x') || 'N/A'}</span>
              <span>Latency {camera.latency_ms || 0}ms</span>
              <span>Loss {camera.packet_loss_pct || 0}%</span>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={() => callCameraAction(camera.camera_id, 'connect')} className="text-xs px-2 py-1 rounded bg-green-500/10 border border-green-500/30 text-green-300">Connect</button>
              <button onClick={() => callCameraAction(camera.camera_id, 'disconnect')} className="text-xs px-2 py-1 rounded bg-red-500/10 border border-red-500/30 text-red-300 flex items-center gap-1"><PowerOff size={12} /> Disconnect</button>
              <button onClick={() => callCameraAction(camera.camera_id, 'restart')} className="text-xs px-2 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-center gap-1"><RotateCcw size={12} /> Restart</button>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default CameraManagerPanel;
