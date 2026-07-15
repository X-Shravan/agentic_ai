import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Camera, Clock } from 'lucide-react';

function CameraFeed() {
  const [frameData, setFrameData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchFrame = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000/api'}/camera/frame`);
        if (response.ok) {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          setFrameData(url);
          setIsLoading(false);
        }
      } catch (error) {
        console.log('Waiting for camera feed...');
        setIsLoading(true);
      }
    };

    // Fetch frame periodically
    const interval = setInterval(fetchFrame, 500); // Update every 500ms for smooth video

    return () => clearInterval(interval);
  }, []);

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
        <div className="flex items-center space-x-2 bg-green-500/20 border border-green-500/30 rounded-full px-3 py-1">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-green-400 text-sm">LIVE</span>
        </div>
      </div>

      <div className="relative bg-gray-900 rounded-xl overflow-hidden">
        {/* Live Camera Feed */}
        <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center relative">
          {frameData ? (
            <img
              src={frameData}
              alt="Live Camera Feed"
              className="w-full h-full object-cover"
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