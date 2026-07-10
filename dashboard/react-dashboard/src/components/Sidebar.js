import React from 'react';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Camera,
  Users,
  AlertTriangle,
  BarChart3,
  FileText,
  Settings,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

const menuItems = [
  { icon: LayoutDashboard, label: 'Dashboard', active: true },
  { icon: Camera, label: 'Live Feed' },
  { icon: Users, label: 'Students' },
  { icon: AlertTriangle, label: 'Alerts' },
  { icon: BarChart3, label: 'Analytics' },
  { icon: FileText, label: 'Reports' },
  { icon: Settings, label: 'Settings' },
];

function Sidebar({ isConnected }) {
  return (
    <motion.div
      initial={{ x: -250 }}
      animate={{ x: 0 }}
      className="w-64 bg-dark-card border-r border-gray-800 flex flex-col"
    >
      {/* Logo */}
      <div className="p-6 border-b border-gray-800">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-neon-blue to-neon-purple bg-clip-text text-transparent">
          AI Surveillance
        </h1>
      </div>

      {/* Menu */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {menuItems.map((item, index) => (
            <motion.li
              key={item.label}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <a
                href="#"
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                  item.active
                    ? 'bg-gradient-to-r from-neon-blue/20 to-neon-purple/20 border border-neon-blue/30 text-neon-blue'
                    : 'hover:bg-gray-800 text-gray-300 hover:text-white'
                }`}
              >
                <item.icon size={20} />
                <span>{item.label}</span>
              </a>
            </motion.li>
          ))}
        </ul>
      </nav>

      {/* System Status */}
      <div className="p-4 border-t border-gray-800">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="bg-dark-card rounded-xl p-4 border border-gray-700"
        >
          <div className="flex items-center space-x-2 mb-3">
            {isConnected ? (
              <>
                <CheckCircle className="text-neon-green" size={16} />
                <span className="text-sm font-medium text-neon-green">Connected to System</span>
              </>
            ) : (
              <>
                <AlertCircle className="text-neon-orange animate-pulse" size={16} />
                <span className="text-sm font-medium text-neon-orange">Connecting...</span>
              </>
            )}
          </div>

          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex justify-between">
              <span>Model:</span>
              <span className="text-neon-blue">YOLOv8</span>
            </div>
            <div className="flex justify-between">
              <span>Backend:</span>
              <span className={isConnected ? 'text-neon-green' : 'text-neon-orange'}>
                {isConnected ? 'Connected' : 'Connecting'}
              </span>
            </div>
          </div>

          <div className="mt-3 bg-gray-800 rounded-full h-2">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: isConnected ? '100%' : '50%' }}
              transition={{ delay: 1, duration: 1 }}
              className="bg-gradient-to-r from-neon-blue to-neon-green h-2 rounded-full"
            />
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

export default Sidebar;