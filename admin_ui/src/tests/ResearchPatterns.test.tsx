import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ResearchPatternsPage } from '../pages/ResearchPatterns';
import * as client from '../api/client';
import type { PatternFindingResponse } from '../api/types';

vi.mock('../api/client', () => ({
  getResearchPatterns: vi.fn(),
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

const mockPatternFinding: PatternFindingResponse = {
  id: 'pattern-uuid-111',
  pattern_hash: 'hash_abc123',
  algorithm_version: '1.0',
  version: 1,
  source_event_type: 'earthquake',
  target_event_type: 'tsunami',
  region_label: 'Pacific',
  time_window_days: 7,
  support_count: 5,
  total_source_events: 6,
  total_target_events: 10,
  observed_rate: 0.8333,
  baseline_rate: 0.20,
  lift: 4.1665,
  statistical_confidence: 0.75,
  uncertainty: {
    point_estimate: 0.75,
    lower_bound: 0.67,
    upper_bound: 0.83,
    source: 'well_supported',
  },
  supporting_event_ids: ['id1', 'id2'],
  description: 'Longitudinal pattern: Earthquake is followed by Tsunami in Pacific within 7 days',
  mined_at: '2026-08-07T00:00:00Z',
  created_at: '2026-08-07T00:00:00Z',
};

describe('ResearchPatternsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders research patterns page title and filters', async () => {
    vi.mocked(client.getResearchPatterns).mockResolvedValue([mockPatternFinding]);

    render(
      <MemoryRouter>
        <ResearchPatternsPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/Longitudinal Research Pattern Mining/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. earthquake/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/earthquake → tsunami/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/4.17x Lift/i).length).toBeGreaterThan(0);
    });
  });

  it('handles empty pattern list state gracefully', async () => {
    vi.mocked(client.getResearchPatterns).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <ResearchPatternsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/No longitudinal patterns found matching current criteria/i)).toBeInTheDocument();
    });
  });

  it('handles API errors gracefully', async () => {
    vi.mocked(client.getResearchPatterns).mockRejectedValue(new Error('API failure'));

    render(
      <MemoryRouter>
        <ResearchPatternsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/API failure/i)).toBeInTheDocument();
    });
  });
});
