import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Bell, User, Wifi, WifiOff } from 'lucide-react';

function Header({ isConnected }) {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <motion.header
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="bg-dark-card border-b border-gray-800 p-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-neon-blue to-neon-purple bg-clip-text text-transparent">
            AI Exam Surveillance Dashboard
          </h1>
          <p className="text-gray-400 mt-1">Real-time Monitoring & Analysis System</p>
        </div>

        <div className="flex items-center space-x-6">
          {/* Connection Status */}
          <motion.div
            animate={{ scale: isConnected ? 1 : [1, 1.05, 1] }}
            transition={{ repeat: isConnected ? 0 : Infinity, duration: 1 }}
            className={`flex items-center space-x-2 rounded-full px-4 py-2 ${
              isConnected
                ? 'bg-green-500/20 border border-green-500/30'
                : 'bg-yellow-500/20 border border-yellow-500/30'
            }`}
          >
            {isConnected ? (
              <>
                <Wifi className="text-green-400" size={16} />
                <span className="text-green-400 text-sm font-medium">Live Monitoring</span>
              </>
            ) : (
              <>
                <WifiOff className="text-yellow-400 animate-pulse" size={16} />
                <span className="text-yellow-400 text-sm font-medium">Connecting...</span>
              </>
            )}
          </motion.div>

          {/* Time & Date */}
          <div className="text-right">
            <div className="text-lg font-mono text-neon-blue">
              {currentTime.toLocaleTimeString()}
            </div>
            <div className="text-sm text-gray-400">
              {currentTime.toLocaleDateString()}
            </div>
          </div>

          {/* Notifications */}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            className="relative p-2 rounded-xl bg-gray-800 hover:bg-gray-700 transition-colors"
          >
            <Bell size={20} />
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-neon-red rounded-full" />
          </motion.button>

          {/* User Profile */}
          <motion.div
            whileHover={{ scale: 1.05 }}
            className="flex items-center space-x-3 bg-gray-800 rounded-xl px-4 py-2"
          >
            <div className="w-8 h-8 bg-gradient-to-r from-neon-blue to-neon-purple rounded-full flex items-center justify-center">
              <User size={16} />
            </div>
            <div>
              <div className="text-sm font-medium">Admin</div>
              <div className="text-xs text-gray-400">Supervisor</div>
            </div>
          </motion.div>
        </div>
      </div>
    </motion.header>
  );
}

export default Header;