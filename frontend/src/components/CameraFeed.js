import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Camera, Clock } from 'lucide-react';
import { API_SIMPLE_URL, API_URL } from '../config';

function CameraFeed() {
  const [frameData, setFrameData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cameraStatus, setCameraStatus] = useState('Starting');
  const [errorMessage, setErrorMessage] = useState('');
  const frameUrlRef = useRef(null);

  const cameraApiBase = (API_SIMPLE_URL || API_URL.replace(/\/api\/?$/, '')).replace(/\/api\/?$/, '');

  useEffect(() => {
    const fetchFrame = async () => {
      try {
        const response = await fetch(`${cameraApiBase}/api/camera/frame?t=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`Camera frame request failed (${response.status})`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        if (frameUrlRef.current) {
          URL.revokeObjectURL(frameUrlRef.current);
        }
        frameUrlRef.current = url;
        setFrameData(url);
        setCameraStatus(response.headers.get('X-Camera-Status') || 'Connected');
        setErrorMessage(response.headers.get('X-Camera-Message') || '');
        setIsLoading(false);
      } catch (error) {
        console.log('Waiting for camera feed...', error);
        setCameraStatus('Disconnected');
        setErrorMessage(`Camera feed is not available yet. Make sure api_simple.py is running on ${cameraApiBase} and the webcam is not used by another app.`);
        setIsLoading(true);
      }
    };

    fetchFrame();

    // Fetch frame periodically
    const interval = setInterval(fetchFrame, 500); // Update every 500ms for smooth video

    return () => {
      clearInterval(interval);
      if (frameUrlRef.current) {
        URL.revokeObjectURL(frameUrlRef.current);
      }
    };
  }, [cameraApiBase]);

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
        <div className={`flex items-center space-x-2 rounded-full px-3 py-1 border ${cameraStatus === 'Simulation' ? 'bg-amber-500/20 border-amber-500/30' : cameraStatus === 'Disconnected' ? 'bg-red-500/20 border-red-500/30' : 'bg-green-500/20 border-green-500/30'}`}>
          <div className={`w-2 h-2 rounded-full animate-pulse ${cameraStatus === 'Simulation' ? 'bg-amber-400' : cameraStatus === 'Disconnected' ? 'bg-red-500' : 'bg-green-500'}`} />
          <span className={`text-sm ${cameraStatus === 'Simulation' ? 'text-amber-300' : cameraStatus === 'Disconnected' ? 'text-red-300' : 'text-green-400'}`}>
            {cameraStatus === 'Simulation' ? 'SIMULATION' : cameraStatus === 'Disconnected' ? 'OFFLINE' : 'LIVE'}
          </span>
        </div>
      </div>

      {errorMessage && (
        <div className={`mb-4 rounded-lg border px-3 py-2 text-xs ${cameraStatus === 'Simulation' ? 'bg-amber-500/10 border-amber-500/30 text-amber-200' : 'bg-blue-500/10 border-blue-500/30 text-blue-200'}`}>
          {errorMessage}
        </div>
      )}

      <div className="relative bg-gray-900 rounded-xl overflow-hidden">
        {/* Live Camera Feed */}
        <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center relative">
          {frameData ? (
            <img
              src={frameData}
              alt="Live Camera Feed"
              className="w-full h-full object-cover"
              onError={() => {
                setFrameData(null);
                setIsLoading(true);
                setErrorMessage('Camera frame could not be displayed.');
              }}
            />
          ) : (
            <div className="text-center">
              <Camera size={48} className="text-gray-600 mx-auto mb-2" />
              <p className="text-gray-400">{isLoading ? 'Waiting for camera...' : 'Camera Feed Active'}</p>
            </div>
          )}

          {/* Timestamp */}
          <div className="absolute bottom-4 left-4 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-1 flex items-center space-x-2">
            <Clock size={14} className="text-gray-400" />
            <span className="text-sm text-gray-300">{new Date().toLocaleTimeString()}</span>
          </div>

          {/* Camera label */}
          <div className="absolute bottom-4 right-4 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-1">
            <span className="text-sm text-gray-300">Camera 1 - Main Hall</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default CameraFeed;