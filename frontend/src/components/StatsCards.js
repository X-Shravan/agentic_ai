import React from 'react';
import { motion } from 'framer-motion';
import { Users, UserCheck, AlertTriangle, Shield } from 'lucide-react';

function StatsCards({ data }) {
  const stats = [
    {
      icon: Users,
      label: 'Total Students Detected',
      value: data?.total_students || 0,
      trend: '↑ 3 from last hour',
      color: 'from-neon-blue to-blue-600',
      glow: 'shadow-neon-blue/20'
    },
    {
      icon: UserCheck,
      label: 'Active IDs',
      value: data?.active_ids || 0,
      trend: '↑ 1 from last hour',
      color: 'from-neon-green to-green-600',
      glow: 'shadow-neon-green/20'
    },
    {
      icon: AlertTriangle,
      label: 'Total Alerts',
      value: data?.total_alerts || 0,
      trend: '↓ 2 from last hour',
      color: 'from-neon-red to-red-600',
      glow: 'shadow-neon-red/20'
    },
    {
      icon: Shield,
      label: 'Normal Students',
      value: data?.normal_students || 0,
      trend: '↑ 4 from last hour',
      color: 'from-neon-purple to-purple-600',
      glow: 'shadow-neon-purple/20'
    }
  ];

  return (
    <div className="space-y-6">
      {stats.map((stat, index) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
          whileHover={{ scale: 1.05 }}
          className={`bg-gradient-to-r ${stat.color} p-6 rounded-2xl shadow-lg ${stat.glow} border border-gray-700`}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center space-x-3 mb-2">
                <stat.icon size={24} className="text-white" />
                <h3 className="text-lg font-semibold text-white">{stat.label}</h3>
              </div>
              <motion.div
                key={stat.value}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring" }}
                className="text-4xl font-bold text-white mb-1"
              >
                {stat.value}
              </motion.div>
              <p className="text-white/80 text-sm">{stat.trend}</p>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

export default StatsCards;