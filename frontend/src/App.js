import React, { useCallback, useEffect, useState } from 'react';
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

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080/api';
const SOCKET_URL = process.env.REACT_APP_SOCKET_URL || ''; // Leave empty for api_simple.py HTTP polling mode

const INITIAL_DASHBOARD_DATA = {
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
};

const INITIAL_TIMELINE_DATA = {
  timestamps: [],
  alert_counts: []
};

function useBackendData() {
  const [dashboardData, setDashboardData] = useState(INITIAL_DASHBOARD_DATA);
  const [isConnected, setIsConnected] = useState(false);
  const [socketConnected, setSocketConnected] = useState(false);
  const [timelineData, setTimelineData] = useState(INITIAL_TIMELINE_DATA);

  useEffect(() => {
    // Connect to SocketIO only when a Socket.IO backend is configured.
    if (!SOCKET_URL) {
      return undefined;
    }

  const refresh = useCallback(async () => {
    try {
      const [students, cameras, alerts, evidence, reports, health, analytics, webrtc] = await Promise.allSettled([
        fetchJson('/students'), fetchJson('/cameras'), fetchJson('/alerts'), fetchJson('/alerts/evidence'),
        fetchJson('/reports'), fetchJson('/health'), fetchJson('/analytics/dashboard'), fetchJson('/webrtc/cameras/status')
      ]);
      setState((prev) => ({
        ...prev,
        students: students.status === 'fulfilled' ? asArray(students.value) : prev.students,
        cameras: cameras.status === 'fulfilled' ? asArray(cameras.value) : prev.cameras,
        alerts: alerts.status === 'fulfilled' ? asArray(alerts.value) : prev.alerts,
        evidence: evidence.status === 'fulfilled' ? asArray(evidence.value) : prev.evidence,
        reports: reports.status === 'fulfilled' ? asArray(reports.value) : prev.reports,
        health: health.status === 'fulfilled' ? health.value : prev.health,
        analytics: analytics.status === 'fulfilled' ? analytics.value : prev.analytics,
        webrtc: webrtc.status === 'fulfilled' ? webrtc.value : prev.webrtc,
        loading: false,
        error: [students, cameras, alerts, evidence, reports, health, analytics].find((r) => r.status === 'rejected')?.reason?.message || null,
        lastSync: new Date().toISOString(),
      }));
      setIsConnected(true);
    });

    socket.on('connection_response', () => {
      console.log('✅ Connection response received');
      setIsConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('❌ Disconnected from WebSocket');
      setSocketConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.log('⚠️ Connection error:', error);
    });

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/dashboard`);
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
        setIsConnected(true);
      }
    } catch (error) {
      console.log('Waiting for API server...');
      if (!socketConnected) {
        setIsConnected(false);
      }
    }
  }, [socketConnected]);

  const fetchTimeline = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/analytics/timeline`);
      if (response.ok) {
        const data = await response.json();
        setTimelineData(data);
      }
    } catch (error) {
      // Silent error for timeline fetch
    }
  }, []);

  // Fetch data periodically via HTTP (as fallback and for initial/cached data)
  useEffect(() => {
    fetchData();
    fetchTimeline();

  const selectedStudent = useMemo(() => data.students.find((s) => s.student_id === selectedStudentId) || data.students[0], [data.students, selectedStudentId]);

  useEffect(() => { if (selectedStudent && !selectedStudentId) setSelectedStudentId(selectedStudent.student_id); }, [selectedStudent, selectedStudentId]);
  useEffect(() => {
    if (!selectedStudentId) return;
    data.fetchJson(`/students/${selectedStudentId}`).then(setStudentDetail).catch(() => setStudentDetail(selectedStudent || null));
  }, [selectedStudentId, data.fetchJson, selectedStudent]);

  const metrics = useMemo(() => {
    const online = data.cameras.filter((c) => ['streaming', 'online', 'registered'].includes(String(c.status).toLowerCase())).length;
    const highAlerts = data.alerts.filter((a) => ['high', 'critical'].includes(String(a.severity || a.risk_level).toLowerCase()) || Number(a.risk_score) >= 60).length;
    const avgFps = data.cameras.length ? data.cameras.reduce((sum, c) => sum + Number(c.fps || 0), 0) / data.cameras.length : 0;
    const avgRisk = data.alerts.length ? data.alerts.reduce((sum, a) => sum + Number(a.risk_score || a.score || 0), 0) / data.alerts.length : 0;
    return [
      ['Students Present', data.students.length, `${data.students.filter((s) => s.seat).length} seated`, Users],
      ['Students Detected', data.analytics?.total_students ?? data.students.filter((s) => s.tracking_id).length, 'YOLO tracked IDs', Shield],
      ['Active Cameras', online, `${data.cameras.length} registered`, Camera],
      ['Active Alerts', data.alerts.length, `${highAlerts} high/critical`, AlertTriangle],
      ['AI Confidence', pct(100 - Math.min(avgRisk, 100)), 'from risk distribution', Brain],
      ['Average FPS', avgFps.toFixed(1), 'camera heartbeat', Gauge],
    ];
  }, [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return {
      students: data.students.filter((s) => JSON.stringify(s).toLowerCase().includes(q)),
      alerts: data.alerts.filter((a) => JSON.stringify(a).toLowerCase().includes(q)),
      cameras: data.cameras.filter((c) => JSON.stringify(c).toLowerCase().includes(q)),
    };
  }, [fetchData, fetchTimeline]);

  return { dashboardData, isConnected, timelineData };
}

function App() {
  const { dashboardData, isConnected, timelineData } = useBackendData();

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
            <Analytics cheatingTypes={dashboardData.cheating_types} />
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
