import { useCallback, useEffect, useRef, useState } from 'react';

type WebSocketStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'reconnecting' | 'error';

export function useWebSocket(url: string, options: { reconnect?: boolean; reconnectMs?: number } = {}) {
  const { reconnect = true, reconnectMs = 3000 } = options;
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(reconnect);
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    shouldReconnectRef.current = reconnect;
  }, [reconnect]);

  const sendJson = useCallback((payload: unknown) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (!url) return undefined;

    let closedByEffect = false;

    const connect = (isReconnect = false) => {
      setStatus(isReconnect ? 'reconnecting' : 'connecting');
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus('open');
        setError(null);
      };

      socket.onmessage = setLastMessage;

      socket.onerror = () => {
        setStatus('error');
        setError('Realtime connection failed');
      };

      socket.onclose = () => {
        socketRef.current = null;
        if (closedByEffect) {
          setStatus('closed');
          return;
        }

        setStatus(shouldReconnectRef.current ? 'reconnecting' : 'closed');
        if (shouldReconnectRef.current) {
          reconnectTimerRef.current = window.setTimeout(() => connect(true), reconnectMs);
        }
      };
    };

    connect(false);

    return () => {
      closedByEffect = true;
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [reconnectMs, url]);

  return { lastMessage, status, error, sendJson };
}
