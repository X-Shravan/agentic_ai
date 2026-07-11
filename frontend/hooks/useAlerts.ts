import { useMemo } from 'react';
import { useWebSocket } from './useWebSocket';

export function useAlerts(url = '') {
  const { lastMessage } = useWebSocket(url);
  return useMemo(() => lastMessage ? JSON.parse(lastMessage.data) : [], [lastMessage]);
}
