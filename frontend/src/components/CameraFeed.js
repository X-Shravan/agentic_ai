import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Camera, Clock, Plus, Trash2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080/api';
const FASTAPI_URL = process.env.REACT_APP_FASTAPI_URL || 'http://localhost:8000/api';

function CameraFeed() {
  const [frameData, setFrameData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState('demo_cam');
  const [cameraForm, setCameraForm] = useState({ camera_id: '', name: '', type: 'webcam', device_index: 0, url: '', resolution: '1280x720', fps: 30, enabled: true });
  const [cameraError, setCameraError] = useState('');

  const loadCameras = async () => {
    try {
      const response = await fetch(`${FASTAPI_URL}/cameras`);
      if (response.ok) {
        const data = await response.json();
        setCameras(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      setCameraError('Camera API unavailable; live frame polling will continue.');
    }
  };

  useEffect(() => {
    loadCameras();
    const cameraInterval = setInterval(loadCameras, 5000);
    return () => clearInterval(cameraInterval);
  }, []);

  useEffect(() => {
    const fetchFrame = async () => {
      try {
        const response = await fetch(`${API_URL}/camera/frame?camera_id=${encodeURIComponent(selectedCamera)}`);
        if (response.ok) {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          setFrameData((previousUrl) => {
            if (previousUrl) URL.revokeObjectURL(previousUrl);
            return url;
          });
          setIsLoading(false);
        }
      } catch (error) {
        console.log('Waiting for camera feed...');
        setIsLoading(true);
      }
    };

    const interval = setInterval(fetchFrame, 500);
    return () => clearInterval(interval);
  }, [selectedCamera]);

  const saveCamera = async (event) => {
    event.preventDefault();
    setCameraError('');
    const [width, height] = cameraForm.resolution.split('x').map((value) => Number(value));
    const payload = {
      camera_id: cameraForm.camera_id || `CAM_${Date.now()}`,
      name: cameraForm.name || cameraForm.camera_id,
      type: cameraForm.type,
      device_index: ['webcam', 'usb'].includes(cameraForm.type) ? Number(cameraForm.device_index) : undefined,
      url: ['rtsp', 'http', 'mjpeg', 'droidcam', 'file'].includes(cameraForm.type) ? cameraForm.url : undefined,
      resolution: [width || 1280, height || 720],
      fps: Number(cameraForm.fps) || 30,
      enabled: cameraForm.enabled,
    };
    try {
      const response = await fetch(`${FASTAPI_URL}/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await response.text());
      await loadCameras();
      setSelectedCamera(payload.camera_id);
    } catch (error) {
      setCameraError(`Camera save failed: ${error.message}`);
    }
  };

  const removeCamera = async (cameraId) => {
    try {
      await fetch(`${FASTAPI_URL}/cameras/${cameraId}`, { method: 'DELETE' });
      await loadCameras();
    } catch (error) {
      setCameraError(`Remove failed: ${error.message}`);
    }
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center space-x-2">
          <Camera className="text-neon-blue" />
          <span>Live Camera Feed - Classroom 1</span>
        </h2>
        <select value={selectedCamera} onChange={(event) => setSelectedCamera(event.target.value)} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm">
          <option value="demo_cam">Demo Camera</option>
          {cameras.map((camera) => <option key={camera.camera_id} value={camera.camera_id}>{camera.name || camera.camera_id} · {camera.status || 'registered'}</option>)}
        </select>
      </div>

      <div className="relative bg-gray-900 rounded-xl overflow-hidden">
        <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center relative">
          {frameData ? (
            <img src={frameData} alt="Live Camera Feed" className="w-full h-full object-cover" />
          ) : (
            <div className="text-center">
              <Camera size={48} className="text-gray-600 mx-auto mb-2" />
              <p className="text-gray-400">{isLoading ? 'Waiting for camera...' : 'Camera Feed Active'}</p>
            </div>
          )}

          <div className="absolute bottom-4 left-4 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-1 flex items-center space-x-2">
            <Clock size={14} className="text-gray-400" />
            <span className="text-sm text-gray-300">{new Date().toLocaleTimeString()}</span>
          </div>
          <div className="absolute bottom-4 right-4 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-1">
            <span className="text-sm text-gray-300">{selectedCamera}</span>
          </div>
        </div>
      </div>

      <form onSubmit={saveCamera} className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <input className="bg-gray-900 border border-gray-700 rounded px-2 py-2" placeholder="Camera ID" value={cameraForm.camera_id} onChange={(e) => setCameraForm({ ...cameraForm, camera_id: e.target.value })} />
        <input className="bg-gray-900 border border-gray-700 rounded px-2 py-2" placeholder="Name" value={cameraForm.name} onChange={(e) => setCameraForm({ ...cameraForm, name: e.target.value })} />
        <select className="bg-gray-900 border border-gray-700 rounded px-2 py-2" value={cameraForm.type} onChange={(e) => setCameraForm({ ...cameraForm, type: e.target.value })}>
          <option value="webcam">Laptop Webcam</option><option value="usb">USB Webcam</option><option value="droidcam">DroidCam</option><option value="rtsp">RTSP CCTV</option><option value="mjpeg">HTTP/MJPEG IP Camera</option><option value="file">Local Video File</option>
        </select>
        <input className="bg-gray-900 border border-gray-700 rounded px-2 py-2" placeholder="Device index" value={cameraForm.device_index} onChange={(e) => setCameraForm({ ...cameraForm, device_index: e.target.value })} />
        <input className="col-span-2 bg-gray-900 border border-gray-700 rounded px-2 py-2" placeholder="URL / IP / file path" value={cameraForm.url} onChange={(e) => setCameraForm({ ...cameraForm, url: e.target.value })} />
        <button className="bg-neon-blue/20 border border-neon-blue/40 rounded px-3 py-2 flex items-center justify-center gap-2" type="submit"><Plus size={16} />Add / Update Camera</button>
        <button className="bg-red-500/20 border border-red-500/40 rounded px-3 py-2 flex items-center justify-center gap-2" type="button" onClick={() => removeCamera(selectedCamera)}><Trash2 size={16} />Remove Selected</button>
      </form>
      {cameraError && <p className="text-yellow-400 text-xs mt-2">{cameraError}</p>}
    </motion.div>
  );
}

export default CameraFeed;
