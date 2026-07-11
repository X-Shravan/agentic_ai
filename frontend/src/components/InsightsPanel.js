import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Flame, Smartphone, Clock, Activity } from 'lucide-react';

function InsightsPanel({ monitoringTime, cheatingTypes, timelineData }) {
  const [peakTime, setPeakTime] = useState('No data yet');
  const [peakCount, setPeakCount] = useState(0);

  useEffect(() => {
    // Calculate peak cheating time from timeline data
    if (timelineData && timelineData.timestamps && timelineData.alert_counts) {
      let maxAlerts = 0;
      let maxTimeIndex = -1;

      timelineData.alert_counts.forEach((count, index) => {
        if (count > maxAlerts) {
          maxAlerts = count;
          maxTimeIndex = index;
        }
      });

      if (maxTimeIndex >= 0 && timelineData.timestamps[maxTimeIndex]) {
        const timestamp = new Date(timelineData.timestamps[maxTimeIndex]);
        const formattedTime = timestamp.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true
        });
        setPeakTime(formattedTime);
        setPeakCount(maxAlerts);
      } else if (timelineData.alert_counts.length > 0) {
        setPeakTime('Still monitoring...');
      }
    }
  }, [timelineData]);

  // Find most frequent type
  let mostFrequentType = 'None';
  let mostFrequentCount = 0;
  
  if (cheatingTypes && Object.keys(cheatingTypes).length > 0) {
    for (const [type, count] of Object.entries(cheatingTypes)) {
      if (count > mostFrequentCount) {
        mostFrequentCount = count;
        mostFrequentType = `${type} (${count} times)`;
      }
    }
  }

  const insights = [
    {
      icon: Flame,
      label: 'Peak Cheating Time',
      value: peakTime,
      subtext: peakCount > 0 ? `${peakCount} incidents detected` : '',
      color: 'text-neon-red'
    },
    {
      icon: Smartphone,
      label: 'Most Frequent Type',
      value: mostFrequentType || 'None detected',
      color: 'text-neon-orange'
    },
    {
      icon: Clock,
      label: 'Total Monitoring Time',
      value: monitoringTime || '00:00:00',
      color: 'text-neon-blue'
    }
  ];

  return (
    <motion.div
      className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
    >
      <div className="flex items-center space-x-2 mb-6">
        <Activity className="text-neon-green" />
        <h2 className="text-xl font-semibold">System Insights</h2>
      </div>

      <div className="space-y-4">
        {insights.map((insight, index) => (
          <motion.div
            key={insight.label}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-gradient-to-r from-gray-800 to-gray-900 p-4 rounded-xl border border-gray-700 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-center space-x-3">
              <div className={`p-2 rounded-lg bg-gray-800 ${insight.color}`}>
                <insight.icon size={20} />
              </div>
              <div>
                <p className="text-sm text-gray-400">{insight.label}</p>
                <p className="text-lg font-semibold text-white truncate">{insight.value}</p>
                {insight.subtext && <p className="text-xs text-gray-500 mt-1">{insight.subtext}</p>}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

export default InsightsPanel;