/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, type ReactNode } from 'react';
import { getMetrics } from '../api/client';
import type { MetricsResponse } from '../api/types';
import { usePoller, type PollerState } from '../hooks/usePoller';

const POLL_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

const MetricsContext = createContext<PollerState<MetricsResponse> | null>(null);

interface MetricsProviderProps {
  children: ReactNode;
  fetcher?: () => Promise<MetricsResponse>;
}

export function MetricsProvider({ children, fetcher = getMetrics }: MetricsProviderProps) {
  const state = usePoller(fetcher, POLL_INTERVAL);
  return (
    <MetricsContext.Provider value={state}>
      {children}
    </MetricsContext.Provider>
  );
}

export function useMetrics(): PollerState<MetricsResponse> {
  const context = useContext(MetricsContext);
  if (!context) {
    throw new Error('useMetrics must be used within a MetricsProvider');
  }
  return context;
}
