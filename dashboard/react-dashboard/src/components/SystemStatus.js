import React from 'react';
import { motion } from 'framer-motion';
import { Activity, Camera, Zap, Server } from 'lucide-react';

function SystemStatus({ systemStatus }) {
  if (!systemStatus) {
    return null;
  }

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'active':
      case 'running':
      case 'connected':
      case 'initialized':
        return 'bg-green-500/20 border-green-500 text-green-400';
      case 'starting':
      case 'initializing':
      case 'loading':
        return 'bg-yellow-500/20 border-yellow-500 text-yellow-400 animate-pulse';
      case 'stopped':
      case 'disconnected':
        return 'bg-gray-500/20 border-gray-500 text-gray-400';
      case 'error':
      case 'failed':
        return 'bg-red-500/20 border-red-500 text-red-400';
      default:
        return 'bg-blue-500/20 border-blue-500 text-blue-400';
    }
  };

  const getStatusIcon = (type) => {
    switch (type) {
      case 'monitoring':
        return Activity;
      case 'detection':
        return Zap;
      case 'camera':
        return Camera;
      case 'ai_model':
        return Server;
      default:
        return Activity;
    }
  };

  const statusItems = [
    { label: 'Monitoring', key: 'monitoring' },
    { label: 'Detection', key: 'detection' },
    { label: 'Camera', key: 'camera' },
    { label: 'AI Model', key: 'ai_model' }
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="bg-dark-card border border-gray-800 rounded-xl p-6 mb-6"
    >
      <h3 className="text-lg font-semibold text-gray-200 mb-4">System Status</h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statusItems.map((item) => {
          const Icon = getStatusIcon(item.key);
          const status = systemStatus[item.key] || 'Unknown';
          const colorClass = getStatusColor(status);

          return (
            <motion.div
              key={item.key}
              whileHover={{ scale: 1.02 }}
              className={`border rounded-lg p-4 flex items-start space-x-3 ${colorClass}`}
            >
              <Icon size={20} className="flex-shrink-0 mt-1" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium opacity-75 truncate">
                  {item.label}
                </p>
                <p className="text-sm font-semibold truncate">
                  {status}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Live Indicator */}
      <div className="mt-4 pt-4 border-t border-gray-700 flex items-center space-x-2">
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="w-3 h-3 rounded-full bg-green-500"
        />
        <span className="text-sm text-green-400">System is live and monitoring</span>
      </div>
    </motion.div>
  );
}

export default SystemStatus;
