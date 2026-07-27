import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';

// Default poll interval: 30 s, configurable via VITE_POLL_INTERVAL_MS env var.
const DEFAULT_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

export type PollerState<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T; lastUpdated: Date }
  | { status: 'unreachable'; lastError: ApiError }
  | { status: 'error'; lastError: ApiError };

/**
 * Generic polling hook.
 *
 * @param fetcher   Async function that fetches data from the API.
 * @param interval  Poll interval in milliseconds (defaults to VITE_POLL_INTERVAL_MS or 30 s).
 *
 * Immediately fetches on mount, then repeats every `interval` ms.
 * Cleans up the timer on unmount.
 */
export function usePoller<T>(
  fetcher: () => Promise<T>,
  interval: number = DEFAULT_INTERVAL_MS,
): PollerState<T> {
  const [state, setState] = useState<PollerState<T>>({ status: 'loading' });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Stabilise the fetcher reference so effect deps don't thrash on every render.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const poll = useCallback(async () => {
    try {
      const data = await fetcherRef.current();
      setState({ status: 'ok', data, lastUpdated: new Date() });
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError('unknown', undefined, String(err));
      setState({
        status: apiErr.status === 'unreachable' ? 'unreachable' : 'error',
        lastError: apiErr,
      });
    }
  }, []);

  useEffect(() => {
    void poll();

    timerRef.current = setInterval(() => {
      void poll();
    }, interval);

    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current);
    };
  }, [poll, interval]);

  return state;
}
