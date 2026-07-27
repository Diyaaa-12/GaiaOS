import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Alerts } from '../pages/Alerts';
import * as client from '../api/client';
import type { AlertIncidentResponse } from '../api/types';

vi.mock('../api/client', () => ({
  getAlerts: vi.fn(),
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

const firingIncident: AlertIncidentResponse = {
  id: '11111111-0000-0000-0000-000000000001',
  rule_id: 'aaaaaaaa-0000-0000-0000-000000000001',
  rule_name: 'High p95 Latency',
  severity: 'warning',
  status: 'firing',
  last_value: 980.5,
  threshold: 500.0,
  consecutive_violations: 3,
  fired_at: '2026-07-27T18:00:00Z',
  resolved_at: null,
};

const resolvedIncident: AlertIncidentResponse = {
  id: '11111111-0000-0000-0000-000000000002',
  rule_id: 'aaaaaaaa-0000-0000-0000-000000000002',
  rule_name: 'Low Success Rate',
  severity: 'critical',
  status: 'resolved',
  last_value: 0.8,
  threshold: 0.9,
  consecutive_violations: 1,
  fired_at: '2026-07-27T15:00:00Z',
  resolved_at: '2026-07-27T16:30:00Z',
};

const renderAlerts = () =>
  render(
    <MemoryRouter>
      <Alerts />
    </MemoryRouter>,
  );

describe('Alerts page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders firing alert with the correct Firing badge', async () => {
    vi.mocked(client.getAlerts).mockResolvedValue([firingIncident]);

    renderAlerts();

    await waitFor(() => {
      expect(screen.getByText(/firing/i)).toBeInTheDocument();
    });
    expect(screen.getByText('High p95 Latency')).toBeInTheDocument();
    expect(screen.queryByText(/✅ Resolved/)).not.toBeInTheDocument();
  });

  it('renders resolved alert with the correct Resolved badge', async () => {
    vi.mocked(client.getAlerts).mockResolvedValue([resolvedIncident]);

    renderAlerts();

    await waitFor(() => {
      expect(screen.getByText(/✅ Resolved/)).toBeInTheDocument();
    });
    expect(screen.getByText('Low Success Rate')).toBeInTheDocument();
  });

  it('renders both firing and resolved incidents correctly', async () => {
    vi.mocked(client.getAlerts).mockResolvedValue([firingIncident, resolvedIncident]);

    renderAlerts();

    await waitFor(() => {
      expect(screen.getByText('High p95 Latency')).toBeInTheDocument();
    });
    expect(screen.getByText('Low Success Rate')).toBeInTheDocument();
    expect(screen.getByText(/🔴 Firing/)).toBeInTheDocument();
    expect(screen.getByText(/✅ Resolved/)).toBeInTheDocument();
  });

  it('shows ApiUnreachable banner when fetch throws', async () => {
    const { ApiError } = await import('../api/client');
    vi.mocked(client.getAlerts).mockRejectedValue(
      new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API'),
    );

    renderAlerts();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot reach gaiaos api/i);
  });
});
