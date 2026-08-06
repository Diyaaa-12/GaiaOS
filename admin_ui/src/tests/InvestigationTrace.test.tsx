import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Investigations } from '../pages/Investigations';
import * as client from '../api/client';
import type { InvestigationTraceResponse } from '../api/types';

vi.mock('../api/client', () => ({
  getInvestigationTrace: vi.fn(),
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

const fixtureTraceResponse: InvestigationTraceResponse = {
  investigation_id: '11111111-1111-4111-8111-111111111111',
  schema_version: '1.0',
  metadata: {
    investigation_id: '11111111-1111-4111-8111-111111111111',
    schema_version: '1.0',
    generated_at: '2026-08-06T20:00:00Z',
    status: 'complete',
    complexity_tier: 'moderate',
    created_at: '2026-08-06T19:55:00Z',
    completed_at: '2026-08-06T19:55:05Z',
    confidence: 0.92,
    node_count: 3,
    edge_count: 2,
    has_replan: false,
    has_collaboration: false,
    has_degraded_mode: false,
  },
  nodes: [
    {
      id: 'node_0_supervisor',
      label: 'Supervisor Planner',
      type: 'planning',
      status: 'completed',
      details: { raw_name: 'supervisor' },
    },
    {
      id: 'node_1_air_quality',
      label: 'Air Quality Domain Agent',
      type: 'agent_started',
      status: 'completed',
      details: { evidence_count: 2 },
    },
    {
      id: 'node_2_synthesis',
      label: 'Cross-Domain Synthesis',
      type: 'synthesizing',
      status: 'completed',
      details: { raw_name: 'synthesis' },
    },
  ],
  edges: [
    { id: 'e1', source: 'node_0_supervisor', target: 'node_1_air_quality', type: 'sequential' },
    { id: 'e2', source: 'node_1_air_quality', target: 'node_2_synthesis', type: 'sequential' },
  ],
  summary: {
    evidence_count: 2,
    replan_count: 0,
    critic_flag_count: 0,
    collaboration_event_count: 0,
    degraded_sources: [],
  },
};

const renderInvestigationsPage = (initialPath = '/investigations') =>
  render(
    <MemoryRouter initialEntries={[initialPath]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/investigations" element={<Investigations />} />
        <Route path="/investigations/:id" element={<Investigations />} />
      </Routes>
    </MemoryRouter>,
  );

describe('Investigations Explainability Trace page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders initial search form prompt when no ID is in URL', () => {
    renderInvestigationsPage();
    expect(screen.getByText(/investigation reasoning explorer/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/enter investigation uuid/i)).toBeInTheDocument();
  });

  it('fetches and renders trace graph view when URL parameter is present', async () => {
    vi.mocked(client.getInvestigationTrace).mockResolvedValue(fixtureTraceResponse);

    renderInvestigationsPage('/investigations/11111111-1111-4111-8111-111111111111');

    await waitFor(() => {
      expect(screen.getByTestId('investigation-trace-view')).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Supervisor Planner/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Air Quality Domain Agent/i)).toBeInTheDocument();
    expect(screen.getByText(/Cross-Domain Synthesis/i)).toBeInTheDocument();
    expect(screen.getByText(/Schema v1.0/i)).toBeInTheDocument();
  });

  it('allows clicking nodes to display details in inspection panel', async () => {
    vi.mocked(client.getInvestigationTrace).mockResolvedValue(fixtureTraceResponse);

    renderInvestigationsPage('/investigations/11111111-1111-4111-8111-111111111111');

    await waitFor(() => {
      expect(screen.getByTestId('investigation-trace-view')).toBeInTheDocument();
    });

    const airQualityNode = screen.getByRole('button', { name: /node Air Quality Domain Agent/i });
    fireEvent.click(airQualityNode);

    expect(screen.getByText(/"evidence_count": 2/i)).toBeInTheDocument();
  });

  it('handles ApiError 404 when investigation is not found', async () => {
    const { ApiError } = await import('../api/client');
    vi.mocked(client.getInvestigationTrace).mockRejectedValue(
      new ApiError('unknown', 404, 'Investigation not found'),
    );

    renderInvestigationsPage('/investigations/nonexistent-id');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert')).toHaveTextContent(/investigation nonexistent-id not found/i);
  });
});
