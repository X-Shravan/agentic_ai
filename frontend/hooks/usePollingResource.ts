import { useCallback, useEffect, useRef, useState } from 'react';

type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

export function usePollingResource<T>(
  fetcher: () => Promise<T>,
  options: { intervalMs?: number; enabled?: boolean; initialData?: T } = {},
) {
  const { intervalMs = 15000, enabled = true, initialData } = options;
  const fetcherRef = useRef(fetcher);
  const [data, setData] = useState<T | undefined>(initialData);
  const [status, setStatus] = useState<AsyncStatus>(initialData === undefined ? 'idle' : 'success');
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const refetch = useCallback(async () => {
    if (!enabled) return;

    setStatus((current) => (current === 'success' ? current : 'loading'));
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      setStatus('success');
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to fetch data');
      setStatus('error');
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;

    void refetch();
    const timer = window.setInterval(() => {
      void refetch();
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [enabled, intervalMs, refetch]);

  return {
    data,
    status,
    error,
    isLoading: status === 'loading' && data === undefined,
    isError: status === 'error',
    updatedAt,
    refetch,
  };
}