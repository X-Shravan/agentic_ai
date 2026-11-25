export function websocketBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) return configured.replace(/\/$/, '');

  const apiUrl = process.env.NEXT_PUBLIC_API_URL
    ?? (typeof window !== 'undefined' ? window.location.origin : '');
  return apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '').replace(/\/$/, '');
}

export function alertsWebSocketUrl(userId = 'dashboard', baseUrl = websocketBaseUrl()) {
  return `${baseUrl}/ws/alerts/${encodeURIComponent(userId)}`;
}
