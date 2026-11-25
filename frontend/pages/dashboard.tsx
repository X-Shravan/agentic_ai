'use client';

import { useEffect, useMemo, useState, memo, type ReactNode } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  FiActivity,
  FiAlertTriangle,
  FiBarChart2,
  FiBell,
  FiCamera,
  FiChevronLeft,
  FiChevronRight,
  FiClock,
  FiCpu,
  FiDatabase,
  FiFileText,
  FiGrid,
  FiMenu,
  FiRefreshCw,
  FiSettings,
  FiShield,
  FiUsers,
  FiWifi,
  FiWifiOff,
  FiX,
} from 'react-icons/fi';
import {
  type AlertRecord,
  type CameraRecord,
  type StudentRecord,
  getAlertHistory,
  getCameraManagerStatus,
  getCameras,
  getCheatingTypes,
  getDashboardAnalytics,
  getHealthStatus,
  getReports,
  getRiskHistory,
  getStudents,
  getWebRTCCamerasStatus,
} from '../services/api';
import { alertsWebSocketUrl } from '../services/websocket';
import { useLiveClock } from '../hooks/useLiveClock';
import { usePollingResource } from '../hooks/usePollingResource';
import { useWebSocket } from '../hooks/useWebSocket';
import { WebRTCVideo } from '../components/WebRTCVideo';

type Severity = 'critical' | 'high' | 'medium' | 'low' | 'unknown';
type IconType = typeof FiActivity;

const sidebarItems = [
  { label: 'Dashboard', icon: FiGrid, href: '/dashboard' },
  { label: 'Live Feed', icon: FiCamera, href: '#live-feed' },
  { label: 'Students', icon: FiUsers, href: '#students' },
  { label: 'Alerts', icon: FiAlertTriangle, href: '#alerts' },
  { label: 'Analytics', icon: FiBarChart2, href: '#analytics' },
  { label: 'Reports', icon: FiFileText, href: '/reports' },
  { label: 'Settings', icon: FiSettings, href: '#settings' },
];

const severityColors: Record<Severity, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#facc15',
  low: '#22c55e',
  unknown: '#64748b',
};

function asArray<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function formatTime(value?: string | Date | null) {
  if (!value) return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(value?: string | Date | null) {
  if (!value) return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
}

function normalizeSeverity(value?: string): Severity {
  const normalized = String(value ?? 'unknown').toLowerCase();
  if (normalized === 'critical' || normalized === 'high' || normalized === 'medium' || normalized === 'low') return normalized;
  return 'unknown';
}

function cameraId(camera?: CameraRecord) {
  return String(camera?.camera_id ?? camera?.id ?? 'CAM_01');
}

function cameraName(camera?: CameraRecord) {
  const id = cameraId(camera);
  return String(camera?.name ?? camera?.location ?? `Camera ${id}`);
}

function isCameraOnline(camera?: CameraRecord) {
  const status = String(camera?.webrtc?.status ?? camera?.status ?? '').toLowerCase();
  return Boolean(camera?.online || camera?.connected || camera?.active || ['streaming', 'online', 'connected', 'active'].includes(status));
}

function studentId(student: StudentRecord) {
  return String(student.student_id ?? student.id ?? 'Unknown');
}

function numberFromUnknown(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function riskScore(student: StudentRecord, riskMap: Map<string, Record<string, unknown>>) {
  const direct = numberFromUnknown(student.risk_score ?? student.score, 0);
  const mappedRisk = riskMap.get(studentId(student));
  const mapped = numberFromUnknown(mappedRisk?.risk_score ?? mappedRisk?.score, 0);
  return direct > 0 ? direct : mapped;
}

function riskLevel(student: StudentRecord, score: number, riskMap: Map<string, Record<string, unknown>>) {
  const mappedRisk = riskMap.get(studentId(student));
  const value = String(student.risk_level ?? student.level ?? mappedRisk?.risk_level ?? mappedRisk?.level ?? '').toLowerCase();
  if (value) return value;
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 35) return 'medium';
  return 'low';
}

const StatCard = memo(function StatCard({ title, value, subtitle, icon: Icon, gradient }: { title: string; value: string | number; subtitle: string; icon: IconType; gradient: string }) {
  return (
    <motion.div whileHover={{ y: -4 }} className={`relative overflow-hidden rounded-3xl border border-white/10 p-5 shadow-2xl shadow-black/20 ${gradient}`}>
      <div className="absolute right-0 top-0 h-28 w-28 translate-x-6 -translate-y-8 rounded-full bg-white/20 blur-2xl" />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-white/80">{title}</p>
          <p className="mt-3 text-4xl font-black tracking-tight text-white">{value}</p>
          <p className="mt-2 text-sm text-white/75">{subtitle}</p>
        </div>
        <div className="rounded-2xl bg-white/15 p-3 text-white backdrop-blur-xl">
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </motion.div>
  );
});

const GlassCard = memo(function GlassCard({ children, className = '', id }: { children: ReactNode; className?: string; id?: string }) {
  return <section id={id} className={`glass-panel rounded-3xl p-5 ${className}`}>{children}</section>;
});

const LiveClock = memo(function LiveClock() {
  const now = useLiveClock();
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-right">
      <div className="flex items-center gap-2 text-cyan-300">
        <FiClock /> <span className="font-mono text-lg font-bold">{formatTime(now)}</span>
      </div>
      <p className="text-xs text-slate-500">{formatDate(now)}</p>
    </div>
  );
});

export default function DashboardPage() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [liveAlerts, setLiveAlerts] = useState<AlertRecord[]>([]);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const alertSocketUrl = useMemo(() => alertsWebSocketUrl('dashboard'), []);
  const alertsSocket = useWebSocket(alertSocketUrl, { reconnect: true, reconnectMs: 3000 });

  const health = usePollingResource(getHealthStatus, { intervalMs: 10000 });
  const cameras = usePollingResource(getCameras, { intervalMs: 12000, initialData: [] });
  const cameraStatus = usePollingResource(getCameraManagerStatus, { intervalMs: 12000 });
  const webrtcStatus = usePollingResource(getWebRTCCamerasStatus, { intervalMs: 8000 });
  const students = usePollingResource(getStudents, { intervalMs: 10000, initialData: [] });
  const alertHistory = usePollingResource(() => getAlertHistory(25), { intervalMs: 8000 });
  const analytics = usePollingResource(getDashboardAnalytics, { intervalMs: 15000 });
  const cheatingTypes = usePollingResource(getCheatingTypes, { intervalMs: 20000 });
  const riskHistory = usePollingResource(getRiskHistory, { intervalMs: 15000, initialData: [] });
  const reports = usePollingResource(getReports, { intervalMs: 30000, initialData: [] });

  useEffect(() => {
    if (!alertsSocket.lastMessage) return;
    try {
      const payload = JSON.parse(alertsSocket.lastMessage.data);
      if (payload?.type === 'alert' && payload.data) {
        setLiveAlerts((current) => [payload.data, ...current].slice(0, 15));
      }
    } catch {
      // Ignore malformed realtime payloads and keep polling fallback visible.
    }
  }, [alertsSocket.lastMessage]);

  useEffect(() => {
    if (alertsSocket.status === 'open') {
      alertsSocket.sendJson({ type: 'subscribe', camera_id: 'global' });
    }
  }, [alertsSocket.status, alertsSocket.sendJson]);

  const cameraList = asArray(cameras.data);
  const studentList = asArray(students.data);
  const reportList = asArray(reports.data);
  const primaryCamera = cameraList[0];
  const primaryCameraId = primaryCamera ? cameraId(primaryCamera) : (Object.keys(webrtcStatus.data?.cameras ?? {})[0] || 'webcam_0');
  const mergedAlerts = useMemo(() => {
    const history = asArray(alertHistory.data?.alerts);
    const seen = new Set<string>();
    return [...liveAlerts, ...history].filter((alert, index) => {
      const id = String(alert.alert_id ?? alert.id ?? `${alert.student_id ?? 'unknown'}-${alert.timestamp ?? alert.created_at ?? index}`);
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    }).slice(0, 12);
  }, [alertHistory.data?.alerts, liveAlerts]);

  const riskMap = useMemo(() => {
    const map = new Map<string, Record<string, unknown>>();
    asArray(riskHistory.data).forEach((risk) => {
      const id = String(risk.student_id ?? '');
      if (id) map.set(id, risk);
    });
    analytics.data?.high_risk_students?.forEach((risk) => {
      const id = String(risk.student_id ?? '');
      if (id && !map.has(id)) map.set(id, risk);
    });
    return map;
  }, [analytics.data?.high_risk_students, riskHistory.data]);

  const enrichedStudents = useMemo(() => studentList.map((student) => {
    const score = riskScore(student, riskMap);
    return { student, score, level: riskLevel(student, score, riskMap) };
  }).sort((a, b) => b.score - a.score), [riskMap, studentList]);

  const totalStudents = analytics.data?.total_students ?? studentList.length;
  const totalAlerts = analytics.data?.total_alerts ?? alertHistory.data?.total ?? mergedAlerts.length;
  const activeIds = new Set(studentList.map(studentId)).size;
  const onlineCameras = cameraList.filter(isCameraOnline).length || numberFromUnknown(health.data?.cameras_registered, 0);
  const backendOnline = health.status === 'success' && health.data?.status === 'healthy';
  const realtimeOnline = alertsSocket.status === 'open';
  const reconnecting = alertsSocket.status === 'reconnecting' || alertsSocket.status === 'connecting';

  const trendData = useMemo(() => asArray(analytics.data?.alert_trends).map((item) => ({
    time: formatTime(item.timestamp),
    alerts: Number(item.alert_count ?? 0),
  })).slice(-12), [analytics.data?.alert_trends]);

  const behaviorData = useMemo(() => Object.entries(analytics.data?.behavior_counts ?? cheatingTypes.data?.cheating_types ?? {}).map(([name, value]) => ({ name, value })), [analytics.data?.behavior_counts, cheatingTypes.data?.cheating_types]);
  const severityData = useMemo(() => Object.entries(analytics.data?.severity_counts ?? {}).map(([name, value]) => ({ name, value, severity: normalizeSeverity(name) })), [analytics.data?.severity_counts]);
  const anyError = [health.error, cameras.error, students.error, alertHistory.error, analytics.error, reports.error].filter(Boolean)[0];

  const SidebarContent = (
    <>
      <div className="flex items-center justify-between gap-3 px-4 py-5">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-400/15 text-cyan-300 shadow-lg shadow-cyan-500/10">
            <FiShield className="h-6 w-6" />
          </div>
          {!sidebarCollapsed && <div><p className="text-lg font-black text-gradient-cyan">AI Surveillance</p><p className="text-xs text-slate-500">Enterprise Console</p></div>}
        </Link>
        <button className="hidden rounded-xl border border-white/10 p-2 text-slate-400 hover:text-white lg:block" onClick={() => setSidebarCollapsed((value) => !value)}>
          {sidebarCollapsed ? <FiChevronRight /> : <FiChevronLeft />}
        </button>
        <button className="rounded-xl border border-white/10 p-2 text-slate-400 hover:text-white lg:hidden" onClick={() => setMobileSidebarOpen(false)}>
          <FiX />
        </button>
      </div>
      <nav className="space-y-2 px-3">
        {sidebarItems.map((item) => (
          <Link key={item.label} href={item.href} className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition ${item.label === 'Dashboard' ? 'bg-cyan-400/15 text-cyan-200 ring-1 ring-cyan-400/20' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}>
            <item.icon className="h-5 w-5 shrink-0" />
            {!sidebarCollapsed && <span>{item.label}</span>}
          </Link>
        ))}
      </nav>
      {!sidebarCollapsed && (
        <div className="mx-4 mt-auto rounded-3xl border border-cyan-400/15 bg-cyan-400/10 p-4 text-sm text-slate-300">
          <p className="font-semibold text-cyan-100">Backend Contract</p>
          <p className="mt-2 text-xs leading-5 text-slate-400">Using existing REST, WebSocket, and WebRTC endpoints without changing payloads.</p>
        </div>
      )}
    </>
  );

  return (
    <div className="enterprise-grid min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_34%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.16),transparent_28%),radial-gradient(circle_at_bottom,rgba(168,85,247,0.12),transparent_34%)]" />

      <aside className={`fixed inset-y-0 left-0 z-40 hidden border-r border-white/10 bg-slate-950/75 backdrop-blur-2xl transition-all duration-300 lg:flex lg:flex-col ${sidebarCollapsed ? 'w-24' : 'w-72'}`}>
        {SidebarContent}
      </aside>

      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileSidebarOpen(false)} />
          <aside className="relative flex h-full w-80 flex-col border-r border-white/10 bg-slate-950/95 backdrop-blur-2xl">
            {SidebarContent}
          </aside>
        </div>
      )}

      <div className={`relative z-10 transition-all duration-300 ${sidebarCollapsed ? 'lg:pl-24' : 'lg:pl-72'}`}>
        <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/70 px-4 py-4 backdrop-blur-2xl sm:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-4">
              <button onClick={() => setMobileSidebarOpen(true)} className="rounded-2xl border border-white/10 p-3 text-slate-300 lg:hidden"><FiMenu /></button>
              <div>
                <h1 className="text-2xl font-black tracking-tight sm:text-3xl"><span className="text-gradient-cyan">AI Exam Surveillance</span> Dashboard</h1>
                <p className="text-sm text-slate-400">Real-time monitoring, alerts, analytics, reports, and camera operations.</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold ${backendOnline ? 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200' : reconnecting ? 'border-amber-400/25 bg-amber-400/10 text-amber-200' : 'border-red-400/25 bg-red-400/10 text-red-200'}`}>
                {backendOnline ? <FiWifi /> : reconnecting ? <FiRefreshCw className="animate-spin" /> : <FiWifiOff />}
                {backendOnline ? 'Backend Online' : reconnecting ? 'Connecting...' : 'Disconnected'}
              </div>
              <LiveClock />
              <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-2">
                <div className="relative flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 text-white"><FiBell /><span className="absolute right-0 top-0 h-3 w-3 rounded-full bg-red-400" /></div>
                <div><p className="text-sm font-semibold">Admin</p><p className="text-xs text-slate-500">Supervisor</p></div>
              </div>
            </div>
          </div>
        </header>

        <main className="space-y-6 p-4 sm:p-6">
          {anyError && <div className="rounded-3xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-100"><span className="font-semibold">API warning:</span> {anyError}. The dashboard will keep retrying automatically.</div>}

          <GlassCard>
            <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div><p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">System Status</p><h2 className="mt-1 text-xl font-bold text-white">AI Monitoring Runtime</h2></div>
              <p className="text-sm text-slate-400">Last refresh: {formatTime(health.updatedAt ?? cameras.updatedAt ?? null)}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatusTile icon={FiActivity} label="Monitoring" value={backendOnline ? 'Operational' : health.isLoading ? 'Loading' : 'Offline'} good={backendOnline} />
              <StatusTile icon={FiCpu} label="Detection" value={`${analytics.data?.high_risk_students?.length ?? 0} high-risk IDs`} good={backendOnline} />
              <StatusTile icon={FiCamera} label="Camera" value={`${onlineCameras}/${Math.max(cameraList.length, onlineCameras)} online`} good={onlineCameras > 0} />
              <StatusTile icon={FiDatabase} label="AI Model" value={health.data?.webrtc_server ?? 'Checking'} good={backendOnline} />
            </div>
            <div className="mt-5 border-t border-white/10 pt-4 text-sm text-emerald-300">● System is live and monitoring when backend status is healthy.</div>
          </GlassCard>

          <div className="grid gap-6 xl:grid-cols-[1.45fr_1fr]">
            <GlassCard id="live-feed" className="space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">Live Camera Feed</p><h2 className="text-2xl font-bold text-white">{cameraName(primaryCamera)} Classroom View</h2></div>
                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-xs font-bold uppercase tracking-[0.2em] text-emerald-300">Live</span>
              </div>
              <WebRTCVideo cameraId={primaryCameraId} className="min-h-[420px]" />
              <div className="grid gap-3 text-sm text-slate-400 sm:grid-cols-3">
                <MiniInfo label="Camera ID" value={primaryCameraId} />
                <MiniInfo label="WebRTC Cameras" value={String(Object.keys(webrtcStatus.data?.cameras ?? {}).length)} />
                <MiniInfo label="Manager" value={String(cameraStatus.data?.status ?? cameraStatus.data?.preferred ?? 'Auto')} />
              </div>
            </GlassCard>
            <div className="grid gap-6">
              <StatCard title="Total Students Detected" value={totalStudents} subtitle="From backend analytics/students APIs" icon={FiUsers} gradient="bg-gradient-to-br from-cyan-400 to-blue-600" />
              <StatCard title="Active IDs" value={activeIds} subtitle="Unique IDs currently tracked" icon={FiShield} gradient="bg-gradient-to-br from-emerald-400 to-green-600" />
              <StatCard title="Total Alerts" value={totalAlerts} subtitle="Alert history + realtime WebSocket" icon={FiAlertTriangle} gradient="bg-gradient-to-br from-orange-400 to-red-600" />
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_1.3fr]">
            <GlassCard id="alerts">
              <SectionHeader title="Live Alerts" subtitle={realtimeOnline ? 'Realtime alerts connected' : reconnecting ? 'Realtime reconnecting' : 'Polling fallback active'} action="View All" />
              <div className="mt-5 space-y-3">{mergedAlerts.length === 0 ? <EmptyState icon={FiAlertTriangle} title="No alerts detected" text="All students behaving normally" /> : mergedAlerts.slice(0, 6).map((alert) => <AlertRow key={String(alert.alert_id ?? alert.id ?? alert.timestamp)} alert={alert} />)}</div>
            </GlassCard>
            <GlassCard id="students">
              <SectionHeader title="Student Monitoring Table" subtitle="Connected to /api/students and risk history" action={`${studentList.length} records`} />
              <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">
                <div className="grid grid-cols-5 bg-white/5 px-4 py-3 text-xs font-bold uppercase tracking-[0.16em] text-slate-400"><span>Student</span><span>Seat</span><span>Camera</span><span>Confidence</span><span>Risk</span></div>
                <div className="max-h-[360px] overflow-auto">{enrichedStudents.length === 0 ? <div className="p-6"><EmptyState icon={FiUsers} title="No students detected" text="Waiting for detection events from backend." /></div> : enrichedStudents.slice(0, 12).map(({ student, score, level }) => <div key={studentId(student)} className="grid grid-cols-5 items-center border-t border-white/10 px-4 py-3 text-sm text-slate-300"><span className="font-semibold text-white">{student.name ?? studentId(student)}</span><span>{student.seat ?? '—'}</span><span>{student.camera_id ?? '—'}</span><span>{Math.round(numberFromUnknown(student.last_confidence ?? student.confidence, 0) * 100)}%</span><span><RiskBadge level={level} score={score} /></span></div>)}</div>
              </div>
            </GlassCard>
          </div>

          <div id="analytics" className="grid gap-6 xl:grid-cols-3">
            <GlassCard className="xl:col-span-2">
              <SectionHeader title="Alert Analytics" subtitle="Connected to /api/analytics/dashboard" />
              <div className="mt-5 h-72">
                {!isClient ? (
                  <div className="flex h-full items-center justify-center text-slate-500">Loading charts...</div>
                ) : trendData.length === 0 ? (
                  <EmptyState icon={FiBarChart2} title="No timeline yet" text="Alert trend data will appear once alerts are logged." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trendData}>
                      <defs>
                        <linearGradient id="alertsGradient" x1="0" x2="0" y1="0" y2="1">
                          <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.05} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.14)" />
                      <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid rgba(148,163,184,.2)', borderRadius: 16, color: '#fff' }} />
                      <Area type="monotone" dataKey="alerts" stroke="#22d3ee" strokeWidth={3} fill="url(#alertsGradient)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </GlassCard>
            <GlassCard>
              <SectionHeader title="Severity Mix" subtitle="Backend severity counters" />
              <div className="mt-5 h-72">
                {!isClient ? (
                  <div className="flex h-full items-center justify-center text-slate-500">Loading charts...</div>
                ) : severityData.length === 0 ? (
                  <EmptyState icon={FiActivity} title="No severity data" text="Severity distribution will appear after alerts." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={severityData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}>
                        {severityData.map((entry) => <Cell key={entry.name} fill={severityColors[entry.severity]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid rgba(148,163,184,.2)', borderRadius: 16, color: '#fff' }} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </GlassCard>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <GlassCard>
              <SectionHeader title="Behavior Distribution" subtitle="Connected to cheating type analytics" />
              <div className="mt-5 h-72">
                {!isClient ? (
                  <div className="flex h-full items-center justify-center text-slate-500">Loading charts...</div>
                ) : behaviorData.length === 0 ? (
                  <EmptyState icon={FiBarChart2} title="No behavior events" text="Distribution updates from backend behavior history." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={behaviorData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.14)" />
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid rgba(148,163,184,.2)', borderRadius: 16, color: '#fff' }} />
                      <Bar dataKey="value" radius={[10, 10, 0, 0]} fill="#38bdf8" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </GlassCard>
            <GlassCard><SectionHeader title="Recent Events Timeline" subtitle="Alerts, reports, and detection activity" /><div className="mt-5 space-y-4">{[...mergedAlerts.slice(0, 4).map((alert) => ({ type: 'Alert', title: alert.reason ?? alert.alert_type ?? 'Suspicious behavior', time: alert.timestamp ?? alert.created_at, tone: 'red' })), ...reportList.slice(0, 3).map((report) => ({ type: 'Report', title: String(report.report_id ?? 'Generated report'), time: String(report.generated_at ?? report.created_at ?? ''), tone: 'cyan' }))].slice(0, 6).map((event, index) => <TimelineEvent key={`${event.type}-${index}`} {...event} />)}{mergedAlerts.length === 0 && reportList.length === 0 && <EmptyState icon={FiClock} title="No recent events" text="Events will appear as backend activity is recorded." />}</div></GlassCard>
          </div>

          <GlassCard id="settings"><SectionHeader title="Settings & Reports Overview" subtitle="Uses existing camera/status/report backend contracts" action={`${reportList.length} reports`} /><div className="mt-5 grid gap-4 md:grid-cols-3"><MiniInfo label="Reports Endpoint" value="/api/reports" /><MiniInfo label="Settings Contract" value="POST /api/cameras/config" /><MiniInfo label="WebRTC Offer" value="/api/webrtc/{camera_id}/offer" /></div></GlassCard>
        </main>

        <footer className="border-t border-white/10 px-6 py-5 text-sm text-slate-500">Enterprise AI Exam Surveillance Dashboard • Backend APIs preserved • WebSocket/WebRTC contracts unchanged</footer>
      </div>
    </div>
  );
}

const StatusTile = memo(function StatusTile({ icon: Icon, label, value, good }: { icon: IconType; label: string; value: string; good: boolean }) {
  return <div className={`rounded-2xl border p-4 ${good ? 'border-cyan-400/20 bg-cyan-400/10' : 'border-amber-400/20 bg-amber-400/10'}`}><div className="flex items-center gap-3"><Icon className={good ? 'text-cyan-300' : 'text-amber-300'} /><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p><p className="font-bold text-white">{value}</p></div></div></div>;
});

const MiniInfo = memo(function MiniInfo({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p><p className="mt-2 truncate font-semibold text-white">{value}</p></div>;
});

function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: string }) {
  return <div className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-bold text-white">{title}</h2>{subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}</div>{action && <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-bold text-cyan-200">{action}</span>}</div>;
}

function EmptyState({ icon: Icon, title, text }: { icon: IconType; title: string; text: string }) {
  return <div className="flex min-h-[150px] flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-6 text-center"><Icon className="mb-3 h-8 w-8 text-slate-500" /><p className="font-semibold text-slate-300">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>;
}

const AlertRow = memo(function AlertRow({ alert }: { alert: AlertRecord }) {
  const severity = normalizeSeverity(alert.severity);
  return <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-3"><span className="h-3 w-3 rounded-full" style={{ background: severityColors[severity] }} /><div><p className="font-semibold text-white">{alert.reason ?? alert.message ?? alert.alert_type ?? 'Suspicious behavior'}</p><p className="text-xs text-slate-500">Student {alert.student_id ?? '—'} • {formatTime(alert.timestamp ?? alert.created_at)}</p></div></div><span className="text-xs font-bold uppercase" style={{ color: severityColors[severity] }}>{severity}</span></div></div>;
});

const RiskBadge = memo(function RiskBadge({ level, score }: { level: string; score: number }) {
  const severity = normalizeSeverity(level);
  return <span className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold uppercase" style={{ borderColor: `${severityColors[severity]}55`, color: severityColors[severity], background: `${severityColors[severity]}18` }}><span>{Math.round(score)}</span>{severity}</span>;
});

const TimelineEvent = memo(function TimelineEvent({ type, title, time, tone }: { type: string; title: string; time?: string; tone: string }) {
  return <div className="flex gap-4"><div className={`mt-1 h-3 w-3 rounded-full ${tone === 'red' ? 'bg-red-400' : 'bg-cyan-400'}`} /><div><p className="text-sm font-semibold text-white">{title}</p><p className="text-xs text-slate-500">{type} • {formatTime(time)}</p></div></div>;
});