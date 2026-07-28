import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, BarChart3, Bell, Bot, Brain, Camera, CheckCircle2, Clock,
  Cpu, Download, FileText, Gauge, HeartPulse, LayoutDashboard, Map, RefreshCw,
  Search, Server, Shield, User, Users, Video, Wifi, WifiOff, XCircle
} from 'lucide-react';
import './index.css';

const API_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
const ROOT_BASE = API_BASE.replace(/\/api$/, '');
const WS_BASE = (process.env.REACT_APP_WS_URL || ROOT_BASE.replace(/^http/, 'ws')).replace(/\/$/, '');

const getId = (item, keys) => keys.map((key) => item?.[key]).find(Boolean);
const asArray = (value) => Array.isArray(value) ? value : (value?.alerts || value?.cameras || value?.items || []);
const pct = (value) => `${Number(value || 0).toFixed(value > 10 ? 0 : 1)}%`;
const time = (value) => value ? new Date(value).toLocaleTimeString() : 'No backend timestamp';
const riskClass = (score = 0, level = '') => {
  const normalized = String(level).toLowerCase();
  if (normalized.includes('critical') || score >= 80) return 'critical';
  if (normalized.includes('high') || score >= 60) return 'high';
  if (normalized.includes('medium') || score >= 31) return 'medium';
  return 'normal';
};

function useBackendData() {
  const [state, setState] = useState({ students: [], cameras: [], alerts: [], evidence: [], reports: [], health: null, analytics: null, wsEvents: [], loading: true, error: null, lastSync: null });

  const fetchJson = useCallback(async (path, options) => {
    const response = await fetch(`${path.startsWith('/health') ? ROOT_BASE : API_BASE}${path}`, options);
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return response.json();
  }, []);

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
    } catch (error) {
      setState((prev) => ({ ...prev, loading: false, error: error.message }));
    }
  }, [fetchJson]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/alerts/dashboard-ui`);
    ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', camera_id: 'global' }));
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        wsEvents: [message, ...prev.wsEvents].slice(0, 30),
        alerts: message.type === 'alert' ? [message.data, ...prev.alerts] : prev.alerts,
        lastSync: new Date().toISOString(),
      }));
    };
    ws.onerror = () => setState((prev) => ({ ...prev, error: prev.error || 'WebSocket unavailable; REST polling is active.' }));
    return () => ws.close();
  }, []);

  return { ...state, refresh, fetchJson };
}

function App() {
  const data = useBackendData();
  const [selectedStudentId, setSelectedStudentId] = useState(null);
  const [studentDetail, setStudentDetail] = useState(null);
  const [search, setSearch] = useState('');
  const navItems = useMemo(() => ['Dashboard','Live Surveillance','Classroom Map','Students','Alerts','Evidence','Analytics','AI Agents','Cameras','Reports','System Health'].map((label, index) => ({ label, Icon: [LayoutDashboard,Video,Map,Users,AlertTriangle,FileText,BarChart3,Bot,Camera,Download,HeartPulse][index] })), []);

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
  }, [data.students, data.alerts, data.cameras, search]);

  const generateReport = async () => {
    const sessionId = selectedStudent?.session_id || data.reports[0]?.session_id || 'current-session';
    await data.fetchJson('/reports/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, exam: { title: 'Exam Surveillance Report' }, include_gemini: true }) });
    data.refresh();
  };

  const statusOk = data.health?.status === 'healthy';

  return <div className="shell">
    <aside className="sidebar"><div className="brand"><Shield/><div><b>Agentic AI</b><small>Exam Surveillance System</small></div></div>{navItems.map(({label:n, Icon},i)=><button className={i===0?'active':''} key={n}><Icon size={16}/><span>{n}</span>{n==='Alerts'&&<em>{data.alerts.length}</em>}</button>)}<div className="campus"><Wifi size={16}/><b>Backend</b><span className={statusOk?'ok':'bad'}>{data.health?.status || 'unavailable'}</span></div></aside>
    <main>
      <header className="topbar"><div><h1>Mid-Semester Examination - Computer Science <span>LIVE</span></h1><p>Date: {new Date().toLocaleDateString()} · Time: {new Date().toLocaleTimeString()} · Last Sync: {time(data.lastSync)}</p></div><label className="search"><Search size={16}/><input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search student, roll no, camera, seat, alert..."/></label><button onClick={data.refresh}><RefreshCw size={16}/></button><Bell/></header>
      {data.error && <section className="banner"><WifiOff size={16}/>{data.error}<button onClick={data.refresh}>Retry</button></section>}
      <section className="kpis">{metrics.map(([label,value,sub,Icon])=><article className="card kpi" key={label}><Icon/><small>{label}</small><strong>{value}</strong><span>{sub}</span></article>)}</section>
      <section className="status-strip"><span><CheckCircle2/>AI System Status: {statusOk?'Optimal':'Degraded'}</span><span><Server/>AI Model: YOLOv8 + DeepSORT + Gemini</span><span><Clock/>Backend timestamp: {time(data.health?.timestamp)}</span></section>
      <section className="grid">
        <Panel title="Live Surveillance" icon={Video} className="wide"><div className="camera-grid">{(filtered.cameras.length?filtered.cameras:data.cameras).map((c)=><div className="feed" key={c.camera_id}><div className="feed-head">{c.camera_id}<b>{c.status || 'registered'}</b></div><div className="lens"><Camera/><span>{c.location || c.rtsp_url || 'Camera stream registered in backend'}</span></div><div className="feed-meta">FPS {c.fps ?? '—'} · {Array.isArray(c.resolution)?c.resolution.join('×'):'resolution —'} · peers {c.connected_peers ?? 0}</div></div>)}{!data.cameras.length&&<Empty text="No camera records returned by /api/cameras."/>}</div></Panel>
        <Panel title="Classroom Map" icon={Map}><div className="seats">{Array.from({length:36},(_,i)=>{const seat=`${String.fromCharCode(65+Math.floor(i/6))}${i%6+1}`; const st=data.students.find(s=>s.seat===seat); const cls=riskClass(Number(st?.risk_score), st?.risk_level); return <button key={seat} className={cls} onClick={()=>st&&setSelectedStudentId(st.student_id)}>{seat}<small>{st?.roll_number||st?.student_id||''}</small></button>})}</div><Legend/></Panel>
        <Panel title="Student Profile" icon={User}><StudentProfile student={studentDetail || selectedStudent} alerts={data.alerts} evidence={data.evidence}/></Panel>
        <Panel title="Alert Center" icon={AlertTriangle}><Table rows={filtered.alerts.slice(0,7)} empty="No alerts returned by /api/alerts." cols={[['Time',r=>time(r.timestamp)],['Student',r=>r.student_id],['Camera',r=>r.camera_id],['Severity',r=>r.severity||r.risk_level],['Risk',r=>r.risk_score ?? r.score ?? '—']]}/></Panel>
        <Panel title="Evidence Center" icon={FileText}><Table rows={data.evidence.slice(0,5)} empty="No evidence returned by /api/alerts/evidence." cols={[['Evidence',r=>r.evidence_id],['Student',r=>r.student_id],['Alert',r=>r.alert_id],['Time',r=>time(r.timestamp)],['Review',r=>r.path?<a href={r.path}>Open</a>:'—']]}/></Panel>
        <Panel title="Gemini AI Reasoning" icon={Brain}><p>{data.alerts[0]?.gemini_explanation || data.alerts[0]?.recommendation || 'No Gemini explanation has been returned by the alert/report endpoints yet.'}</p></Panel>
        <Panel title="CrewAI Agents Monitor" icon={Bot}><AgentRows healthy={statusOk}/></Panel>
        <Panel title="Camera Management" icon={Camera} className="wide"><Table rows={data.cameras} empty="No cameras registered." cols={[['Name',r=>r.camera_id],['Type',r=>r.rtsp_url?'RTSP':'Backend'],['Resolution',r=>Array.isArray(r.resolution)?r.resolution.join('×'):'—'],['FPS',r=>r.fps ?? '—'],['Latency',r=>r.latency ?? '—'],['Status',r=>r.status || 'registered']]}/></Panel>
        <Panel title="AI Performance" icon={Cpu}><div className="perf"><b>Detection FPS</b><strong>{metrics[5][1]}</strong><b>Registered Cameras</b><strong>{data.health?.cameras_registered ?? data.cameras.length}</strong><b>Queue / False positives</b><strong>{data.analytics?.queue_length ?? '—'} / {data.analytics?.false_positives ?? '—'}</strong></div></Panel>
        <Panel title="System Health" icon={HeartPulse}><div className="health">{['Backend','Database','Gemini','CrewAI','LangChain','Camera','Storage','WebRTC'].map(x=><span key={x}><i className={statusOk?'okdot':'baddot'}/>{x} {statusOk?'Healthy':'Check backend'}</span>)}</div></Panel>
        <Panel title="Reports" icon={Download}><button className="primary" onClick={generateReport}>Generate backend PDF report</button><Table rows={data.reports.slice(0,4)} empty="No reports returned by /api/reports." cols={[['Report',r=>r.report_id],['Session',r=>r.session_id],['Download',r=>r.report_id?<a href={`${API_BASE}/reports/${r.report_id}/download`}>PDF</a>:'—']]}/></Panel>
      </section>
    </main>
  </div>;
}

function Panel({ title, icon: Icon, children, className='' }) { return <section className={`card panel ${className}`}><h2><Icon size={16}/>{title}</h2>{children}</section>; }
function Empty({ text }) { return <div className="empty"><XCircle/>{text}</div>; }
function Table({ rows, cols, empty }) { return rows?.length ? <div className="table">{rows.map((r,i)=><div className="tr" key={getId(r,['alert_id','camera_id','student_id','evidence_id','report_id'])||i}>{cols.map(([h,fn])=><span key={h} data-label={h}>{fn(r) || '—'}</span>)}</div>)}</div> : <Empty text={empty}/>; }
function Legend(){ return <div className="legend"><span className="normal">Normal</span><span className="medium">Medium</span><span className="high">High</span><span className="critical">Critical</span></div>; }
function StudentProfile({ student, alerts, evidence }) { if (!student) return <Empty text="No student records returned by /api/students."/>; const studentAlerts=alerts.filter(a=>a.student_id===student.student_id); return <div className="profile"><div className="avatar"><User size={48}/></div><h3>{student.name || student.student_id}</h3><p>Roll No. {student.roll_number || '—'} · Seat {student.seat || '—'}</p><p>Tracking ID {student.tracking_id || '—'} · Camera {student.camera_id || '—'}</p><div className="risk-ring">{student.risk_score ?? studentAlerts[0]?.risk_score ?? 0}</div><small>{studentAlerts.length} alerts · {evidence.filter(e=>e.student_id===student.student_id).length} evidence items</small></div>; }
function AgentRows({ healthy }) { return <div className="agents">{['Detection Agent','Tracking Agent','Behavior Agent','Risk Agent','Evidence Agent','Report Agent','Gemini Agent'].map((a)=><span key={a}>{a}<b className={healthy?'ok':'bad'}>{healthy?'Running':'Unknown'}</b></span>)}</div>; }
export default App;
