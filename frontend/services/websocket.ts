export function alertsWebSocketUrl(baseUrl = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000') {
  return `${baseUrl}/ws/alerts`;
}
