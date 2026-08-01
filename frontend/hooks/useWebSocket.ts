import { useEffect, useState } from 'react';

export function useWebSocket(url: string) {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  useEffect(() => { if (!url) return; const socket = new WebSocket(url); socket.onmessage = setLastMessage; return () => socket.close(); }, [url]);
  return { lastMessage };
}
