import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import io from 'socket.io-client';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import SystemStatus from './components/SystemStatus';
import CameraFeed from './components/CameraFeed';
import StatsCards from './components/StatsCards';
import AlertsPanel from './components/AlertsPanel';
import Analytics from './components/Analytics';
import InsightsPanel from './components/InsightsPanel';
import { API_URL, SOCKET_URL } from './config';

function App() {
  const [dashboardData, setDashboardData] = useState({
    total_students: 0,
    active_ids: 0,
    total_alerts: 0,
    normal_students: 0,
    alerts: [],
    cheating_types: {},
    monitoring_time: '00:00:00',
    system_status: {
      monitoring: 'Initializing',
      detection: 'Initializing',
      camera: 'Disconnected',
      ai_model: 'Loading'
    },
    system_running: false
  });

  const [isConnected, setIsConnected] = useState(false);
  const [socketConnected, setSocketConnected] = useState(false);
  const [timelineData, setTimelineData] = useState({
    timestamps: [],
    alert_counts: []
  });

  const normalizeBehaviorType = useCallback((type) => {
    const normalized = String(type || 'Unknown').trim().toLowerCase().replace(/[-\s]+/g, '_');
    const labels = {
      phone_detected: 'Using Mobile',
      mobile_detected: 'Using Mobile',
      using_mobile: 'Using Mobile',
      gaze_sideways: 'Looking Around',
      excessive_turning: 'Looking Around',
      looking_around: 'Looking Around',
      gaze_downward: 'Looking to Copy',
      paper_sharing: 'Looking to Copy',
      looking_to_copy: 'Looking to Copy',
      leaning: 'Leaning'
    };
    return labels[normalized] || normalized.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
  }, []);

  const normalizeSeverity = useCallback((severity) => String(severity || 'MEDIUM').toUpperCase(), []);

  const normalizeAlert = useCallback((alert, index = 0) => {
    const firstBehavior = Array.isArray(alert.behaviors) ? alert.behaviors[0] : null;
    return {
      ...alert,
      id: alert.id || alert.alert_id || alert.event_id || `ALERT-${index + 1}`,
      type: alert.type || normalizeBehaviorType(firstBehavior?.behavior_type || alert.alert_type || alert.reason),
      severity: normalizeSeverity(alert.severity || alert.risk_level),
      timestamp: alert.timestamp || alert.created_at || new Date().toISOString()
    };
  }, [normalizeBehaviorType, normalizeSeverity]);

  const normalizeDashboardData = useCallback((data, previousData) => {
    const alerts = Array.isArray(data.alerts) ? data.alerts.map(normalizeAlert) : previousData.alerts;
    const cheatingTypes = data.cheating_types || data.behavior_counts || previousData.cheating_types || {};
    const totalStudents = data.total_students ?? previousData.total_students ?? 0;
    const totalAlerts = data.total_alerts ?? alerts.length ?? previousData.total_alerts ?? 0;
    const activeIds = data.active_ids ?? totalStudents;

    return {
      ...previousData,
      ...data,
      total_students: totalStudents,
      active_ids: activeIds,
      total_alerts: totalAlerts,
      normal_students: data.normal_students ?? Math.max(0, totalStudents - totalAlerts),
      alerts,
      cheating_types: cheatingTypes,
      monitoring_time: data.monitoring_time || previousData.monitoring_time,
      system_status: data.system_status || {
        monitoring: 'Active',
        detection: 'Running',
        camera: previousData.system_status?.camera || 'Connected',
        ai_model: 'Initialized'
      },
      system_running: data.system_running ?? true
    };
  }, [normalizeAlert]);

  useEffect(() => {
    // Connect to SocketIO only when a Socket.IO backend is configured.
    if (!SOCKET_URL) {
      return undefined;
    }

    const socket = io(SOCKET_URL, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    });

    socket.on('connect', () => {
      console.log('✅ Connected to WebSocket');
      setSocketConnected(true);
      socket.emit('request_update');
    });

    socket.on('surveillance_update', (data) => {
      console.log('📊 Received update:', data);
      setDashboardData(prevData => ({
        ...prevData,
        total_students: data.total_students || prevData.total_students,
        active_ids: data.active_ids || prevData.active_ids,
        total_alerts: data.total_alerts || prevData.total_alerts,
        normal_students: data.normal_students || prevData.normal_students,
        alerts: data.alerts || prevData.alerts,
        cheating_types: data.cheating_types || prevData.cheating_types,
      }));
      setIsConnected(true);
    });

    socket.on('connection_response', (data) => {
      console.log('✅ Connection response:', data);
      setIsConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('❌ Disconnected from WebSocket');
      setSocketConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.log('⚠️ Connection error:', error);
    });

    return () => socket.close();
  }, []);

  // Fetch data periodically via HTTP (as fallback and for initial/cached data)
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [analyticsResponse, historyResponse, cheatingResponse] = await Promise.all([
          fetch(`${API_URL}/analytics/dashboard`),
          fetch(`${API_URL}/alerts/history?limit=25`),
          fetch(`${API_URL}/analytics/cheating-types`)
        ]);

        if (analyticsResponse.ok) {
          const analytics = await analyticsResponse.json();
          const history = historyResponse.ok ? await historyResponse.json() : { alerts: [] };
          const cheating = cheatingResponse.ok ? await cheatingResponse.json() : {};
          setDashboardData(prevData => normalizeDashboardData({
            ...analytics,
            alerts: history.alerts || [],
            cheating_types: cheating.cheating_types || analytics.behavior_counts || {}
          }, prevData));
          setIsConnected(true);
          return;
        }

        const fallbackResponse = await fetch(`${API_URL}/dashboard`);
        if (fallbackResponse.ok) {
          const data = await fallbackResponse.json();
          setDashboardData(prevData => normalizeDashboardData(data, prevData));
          setIsConnected(true);
        }
      } catch (error) {
        console.log('Waiting for API server...');
        if (!socketConnected) {
          setIsConnected(false);
        }
      }
    };

    // Fetch timeline data for peak cheating time calculation
    const fetchTimeline = async () => {
      try {
        const response = await fetch(`${API_URL}/analytics/timeline`);
        if (response.ok) {
          const data = await response.json();
          setTimelineData(data);
        }
      } catch (error) {
        // Silent error for timeline fetch
      }
    };

    // Initial fetch
    fetchData();
    fetchTimeline();

    // Set up polling intervals (less frequent now that we have WebSocket)
    const dashboardInterval = setInterval(fetchData, 2000);
    const timelineInterval = setInterval(fetchTimeline, 3000);

    return () => {
      clearInterval(dashboardInterval);
      clearInterval(timelineInterval);
    };
  }, [socketConnected, normalizeDashboardData]);

  return (
    <div className="min-h-screen bg-dark-bg text-white flex">
      <Sidebar isConnected={isConnected} />
      <div className="flex-1 flex flex-col">
        <Header isConnected={isConnected} />
        <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-auto">
          {/* System Status - Full Width */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="col-span-12"
          >
            <SystemStatus systemStatus={dashboardData.system_status} />
          </motion.div>

          {/* Left Section - Camera Feed */}
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="col-span-12 lg:col-span-5"
          >
            <CameraFeed />
          </motion.div>

          {/* Center Section - Stats */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="col-span-12 lg:col-span-4"
          >
            <StatsCards data={dashboardData} />
          </motion.div>

          {/* Right Section - Alerts */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="col-span-12 lg:col-span-3"
          >
            <AlertsPanel alerts={dashboardData.alerts} />
          </motion.div>

          {/* Bottom Section - Analytics */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
            className="col-span-12 lg:col-span-8"
          >
            <Analytics cheatingTypes={dashboardData.cheating_types} timelineData={timelineData} />
          </motion.div>

          {/* Right Insights */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
            className="col-span-12 lg:col-span-4"
          >
            <InsightsPanel 
              monitoringTime={dashboardData.monitoring_time} 
              cheatingTypes={dashboardData.cheating_types}
              timelineData={timelineData}
            />
          </motion.div>
        </main>
      </div>
    </div>
  );
}

export default App;