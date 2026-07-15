import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { TrendingUp, PieChart as PieChartIcon } from 'lucide-react';

function Analytics({ cheatingTypes }) {
  const [timeData, setTimeData] = useState([]);
  const [pieData, setPieData] = useState([
    { name: 'Using Mobile', value: 0, color: '#ff4444' },
    { name: 'Looking Around', value: 0, color: '#ffaa00' },
    { name: 'Looking to Copy', value: 0, color: '#aa00ff' },
    { name: 'Leaning', value: 0, color: '#00ff88' }
  ]);

  useEffect(() => {
    // Fetch real-time timeline data
    const fetchTimeline = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000/api'}/analytics/timeline`);
        if (response.ok) {
          const data = await response.json();
          
          // Convert timestamps to time format (HH:MM)
          const times = data.timestamps || [];
          const alerts = data.alert_counts || [];
          
          // Create chart data with last 20 entries
          const chartData = times.slice(-20).map((time, index) => {
            const date = new Date(time);
            const timeStr = date.toLocaleTimeString('en-US', { 
              hour: '2-digit', 
              minute: '2-digit',
              hour12: false 
            });
            
            return {
              time: timeStr,
              alerts: alerts[times.length - 20 + index] || 0
            };
          });
          
          setTimeData(chartData);
        }
      } catch (error) {
        console.log('Fetching timeline data...');
      }
    };

    fetchTimeline();
    const timelineInterval = setInterval(fetchTimeline, 2000);

    return () => clearInterval(timelineInterval);
  }, []);

  useEffect(() => {
    if (cheatingTypes && Object.keys(cheatingTypes).length > 0) {
      setPieData([
        { name: 'Using Mobile', value: cheatingTypes['Using Mobile'] || 0, color: '#ff4444' },
        { name: 'Looking Around', value: cheatingTypes['Looking Around'] || 0, color: '#ffaa00' },
        { name: 'Looking to Copy', value: cheatingTypes['Looking to Copy'] || 0, color: '#aa00ff' },
        { name: 'Leaning', value: cheatingTypes['Leaning'] || 0, color: '#00ff88' }
      ]);
    }
  }, [cheatingTypes]);

  const totalAlerts = pieData.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="space-y-6">
      {/* Line Chart - Real-time Alerts */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
      >
        <div className="flex items-center space-x-2 mb-6">
          <TrendingUp className="text-neon-blue" />
          <h2 className="text-xl font-semibold">Real-time Alerts</h2>
          <span className="ml-auto text-sm text-neon-red animate-pulse">● LIVE</span>
        </div>

        <div className="h-64">
          {timeData && timeData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="time"
                  stroke="#9CA3AF"
                  fontSize={12}
                />
                <YAxis
                  stroke="#9CA3AF"
                  fontSize={12}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1F2937',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    color: '#F9FAFB'
                  }}
                  formatter={(value) => [`Alerts: ${value}`, 'Count']}
                />
                <Line
                  type="monotone"
                  dataKey="alerts"
                  stroke="#00d4ff"
                  strokeWidth={3}
                  dot={{ fill: '#00d4ff', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, stroke: '#00d4ff', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-400">
              Waiting for real-time data...
            </div>
          )}
        </div>

        <div className="mt-4 p-3 bg-neon-blue/10 border border-neon-blue/30 rounded-lg">
          <p className="text-neon-blue text-sm font-medium">
            📈 Current Peak: Updates in real-time as alerts happen
          </p>
        </div>
      </motion.div>

      {/* Donut Chart - Cheating Type Distribution */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-dark-card rounded-2xl p-6 border border-gray-800 backdrop-blur-sm"
      >
        <div className="flex items-center space-x-2 mb-6">
          <PieChartIcon className="text-neon-purple" />
          <h2 className="text-xl font-semibold">Cheating Type Distribution</h2>
          <span className="ml-auto text-sm text-neon-red animate-pulse">● LIVE</span>
        </div>

        <div className="h-64 flex items-center justify-center relative">
          {totalAlerts > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1F2937',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    color: '#F9FAFB'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center">
              <p className="text-gray-400 mb-2">No alerts yet</p>
              <p className="text-gray-500 text-sm">Cheating distribution will appear here</p>
            </div>
          )}
          <div className="absolute text-center">
            <div className="text-2xl font-bold text-white">{totalAlerts}</div>
            <div className="text-sm text-gray-400">Total Alerts</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mt-6">
          {pieData.map((item) => (
            <div key={item.name} className="flex items-center space-x-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-sm text-gray-300">{item.name}</span>
              <span className="text-sm text-gray-400">({item.value})</span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

export default Analytics;