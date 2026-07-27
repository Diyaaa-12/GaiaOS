import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Metrics } from '../pages/Metrics';
import { MetricsProvider } from '../context/MetricsContext';
import * as client from '../api/client';
import type { MetricsResponse } from '../api/types';

vi.mock('../api/client', () => ({
  getMetrics: vi.fn(),
  ApiError: class ApiError extends Error {
    status: string;
    httpStatus?: number;
    constructor(status: string, httpStatus?: number, message?: string) {
      super(message ?? status);
      this.status = status;
      this.httpStatus = httpStatus;
      this.name = 'ApiError';
    }
  },
}));

const fixtureMetrics: MetricsResponse = {
  window: '7d',
  group_by: 'complexity_tier',
  rollups: [
    {
      group_key: 'simple',
      count: 120,
      p50_latency_ms: 45.3,
      p95_latency_ms: 112.8,
      avg_cost_estimate: 0.0012,
      success_rate: 0.975,
    },
  ],
  queue_depth: 3,
  worker_utilization_pct: 42.5,
  recommended_pool_size: 2,
};

const renderMetrics = () =>
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <MetricsProvider>
        <Metrics />
      </MetricsProvider>
    </MemoryRouter>,
  );

describe('Metrics page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders metrics table from fixture API response', async () => {
    vi.mocked(client.getMetrics).mockResolvedValue(fixtureMetrics);

    renderMetrics();

    // Initially shows loading state
    expect(screen.getByText(/loading metrics/i)).toBeInTheDocument();

    // After fetch resolves, table is rendered
    await waitFor(() => {
      expect(screen.getByRole('table', { name: undefined })).toBeInTheDocument();
    });

    expect(screen.getByText('simple')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('45.3')).toBeInTheDocument();
    expect(screen.getByText('97.5%')).toBeInTheDocument();
  });

  it('shows ApiUnreachable banner when fetch throws unreachable error', async () => {
    const { ApiError } = await import('../api/client');
    vi.mocked(client.getMetrics).mockRejectedValue(
      new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API'),
    );

    renderMetrics();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot reach gaiaos api/i);
  });
});
