import React from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Smartphone, Eye, Clock } from 'lucide-react';

function AlertsPanel({ alerts }) {
  const getAlertIcon = (type) => {
    switch (type) {
      case 'Using Mobile':
        return Smartphone;
      case 'Looking Around':
      case 'Looking to Copy':
        return Eye;
      case 'Leaning':
        return Clock;
      default:
        return AlertTriangle;
    }
  };

  return (
    <motion.div
      className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center space-x-2">
          <AlertTriangle className="text-neon-red" />
          <span>Live Alerts</span>
        </h2>
        <button className="text-neon-blue hover:text-neon-blue/80 text-sm font-medium transition-colors">
          View All
        </button>
      </div>

      <div className="space-y-4">
        {alerts && alerts.length > 0 ? (
          alerts.map((alert, index) => {
            const Icon = getAlertIcon(alert.type);
            const isHighSeverity = alert.severity === 'HIGH';
            
            return (
              <motion.div
                key={`${alert.id}-${alert.timestamp}`}
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.2 }}
                whileHover={{ scale: 1.02 }}
                className={`p-4 rounded-xl border-l-4 ${
                  isHighSeverity 
                    ? 'border-neon-red bg-neon-red/10' 
                    : 'border-neon-orange bg-neon-orange/10'
                } bg-gray-800/50 backdrop-blur-sm`}
              >
                <div className="flex items-start space-x-3">
                  <div className="w-12 h-8 bg-gray-700 rounded flex items-center justify-center">
                    <Icon size={16} className={isHighSeverity ? 'text-neon-red' : 'text-neon-orange'} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-white">ID: {alert.id}</span>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        isHighSeverity
                          ? 'bg-neon-red/20 text-neon-red'
                          : 'bg-neon-orange/20 text-neon-orange'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-gray-300 text-sm mb-2">{alert.type}</p>
                    <div className="flex items-center space-x-1 text-xs text-gray-400">
                      <Clock size={12} />
                      <span>{new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-400">No alerts detected</p>
            <p className="text-gray-500 text-sm mt-1">All students behaving normally</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default AlertsPanel;