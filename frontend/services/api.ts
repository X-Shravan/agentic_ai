const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;
const browserOrigin = typeof window !== 'undefined' ? window.location.origin : '';

export const API_BASE_URL = (configuredApiUrl ?? browserOrigin).replace(/\/api\/?$/, '').replace(/\/$/, '');
export const API_URL = `${API_BASE_URL}/api`;

export type CameraRecord = {
  id?: string;
  camera_id?: string;
  name?: string;
  location?: string;
  status?: string;
  online?: boolean;
  connected?: boolean;
  active?: boolean;
  fps?: number;
  resolution?: number[];
  students_tracked?: number;
  last_frame_time?: string;
  last_seen?: string;
  webrtc?: Record<string, unknown> & {
    status?: string;
    fps?: number;
    connected_peers?: number;
    students_tracked?: number;
    last_frame_time?: string;
  };
  [key: string]: unknown;
};

export type StudentRecord = {
  student_id?: string;
  id?: string;
  name?: string;
  roll_number?: string;
  email?: string;
  seat?: string;
  camera_id?: string;
  tracking_id?: number;
  track_id?: number;
  last_confidence?: number;
  confidence?: number;
  last_seen?: string;
  risk_score?: number;
  score?: number;
  risk_level?: string;
  level?: string;
  [key: string]: unknown;
};

export type AlertRecord = {
  id?: string;
  alert_id?: string;
  student_id?: string;
  session_id?: string;
  camera_id?: string;
  alert_type?: string;
  risk_score?: number;
  score?: number;
  severity?: string;
  reason?: string;
  message?: string;
  gemini_explanation?: string;
  recommendation?: string;
  timestamp?: string;
  created_at?: string;
  behaviors?: Array<Record<string, unknown>>;
  evidence_captured?: boolean;
  [key: string]: unknown;
};

export type DashboardAnalytics = {
  total_students?: number;
  total_alerts?: number;
  high_risk_students?: Array<Record<string, unknown>>;
  alert_trends?: Array<{ timestamp?: string; alert_count?: number }>;
  severity_counts?: Record<string, number>;
  behavior_counts?: Record<string, number>;
  timestamp?: string;
};

export type TimelineResponse = {
  timestamps?: string[];
  alert_counts?: number[];
  timeline?: Array<{ timestamp?: string; alert_count?: number }>;
  timestamp?: string;
};

export type CheatingTypesResponse = {
  cheating_types?: Record<string, number>;
  total_alerts?: number;
  timestamp?: string;
};

export type ReportRecord = {
  report_id?: string;
  session_id?: string;
  pdf_path?: string;
  summary?: Record<string, unknown> | string;
  generated_at?: string;
  created_at?: string;
  [key: string]: unknown;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorBody = await response.json();
      detail = errorBody?.detail ?? detail;
    } catch {
      // Keep the HTTP status text if the backend did not return JSON.
    }
    throw new Error(`API request failed (${response.status}): ${detail}`);
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T = unknown>(path: string) {
  return requestJson<T>(path);
}

export async function getRootStatus() {
  return requestJson<{ name?: string; version?: string; status?: string; endpoints?: Record<string, string> }>('/');
}

export async function getHealthStatus() {
  return requestJson<{ status?: string; webrtc_server?: string; cameras_registered?: number; timestamp?: string }>('/health');
}

export async function getCameras() {
  return requestJson<CameraRecord[]>('/api/cameras');
}

export async function getCameraManagerStatus() {
  return requestJson<Record<string, unknown>>('/api/cameras/status');
}

export async function getWebRTCCamerasStatus() {
  return requestJson<{ cameras?: Record<string, CameraRecord>; timestamp?: string }>('/api/webrtc/cameras/status');
}

export async function getStudents() {
  return requestJson<StudentRecord[]>('/api/students');
}

export async function getAlertHistory(limit = 50) {
  return requestJson<{ alerts?: AlertRecord[]; total?: number; limit?: number }>('/api/alerts/history?limit=' + limit);
}

export async function getAlerts() {
  return requestJson<AlertRecord[]>('/api/alerts');
}

export async function getRiskHistory() {
  return requestJson<Array<Record<string, unknown>>>('/api/alerts/risk/history');
}

export async function getDashboardAnalytics() {
  return requestJson<DashboardAnalytics>('/api/analytics/dashboard');
}

export async function getAnalyticsTimeline() {
  return requestJson<TimelineResponse>('/api/analytics/timeline');
}

export async function getCheatingTypes() {
  return requestJson<CheatingTypesResponse>('/api/analytics/cheating-types');
}

export async function getHeatmap(cameraId: string) {
  return requestJson<{ camera_id?: string; heatmap?: number[][]; points?: number; timestamp?: string }>(`/api/analytics/heatmap/${cameraId}`);
}

export async function getReports() {
  return requestJson<ReportRecord[]>('/api/reports');
}
