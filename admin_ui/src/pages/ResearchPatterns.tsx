import React, { useCallback, useEffect, useState } from 'react';
import { getResearchPatterns } from '../api/client';
import type { PatternFindingResponse } from '../api/types';
import { PatternGraphView } from '../components/PatternGraphView';

export const ResearchPatternsPage: React.FC = () => {
  const [patterns, setPatterns] = useState<PatternFindingResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [eventType, setEventType] = useState<string>('');
  const [region, setRegion] = useState<string>('');
  const [minConfidence, setMinConfidence] = useState<number>(0.7);
  const [sortBy, setSortBy] = useState<'confidence' | 'support_count' | 'lift' | 'mined_at'>('confidence');
  const [selectedPattern, setSelectedPattern] = useState<PatternFindingResponse | null>(null);

  const fetchPatterns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getResearchPatterns({
        event_type: eventType.trim() || undefined,
        region: region.trim() || undefined,
        min_confidence: minConfidence > 0 ? minConfidence : undefined,
        sort_by: sortBy,
        order: 'desc',
        limit: 100,
      });
      setPatterns(data);
      setSelectedPattern((current) => {
        if (data.length === 0) return null;
        if (current && data.some((p) => p.id === current.id)) return current;
        return data[0];
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch research patterns');
    } finally {
      setLoading(false);
    }
  }, [eventType, region, minConfidence, sortBy]);

  useEffect(() => {
    fetchPatterns();
  }, [fetchPatterns]);

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>
          Longitudinal Research Pattern Mining
        </h1>
        <p style={{ color: '#64748b', fontSize: '0.9rem', marginTop: '0.35rem' }}>
          Statistically significant recurring co-occurrence patterns discovered across multi-source historical hazard data.
        </p>
      </div>

      {/* Filter Bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          backgroundColor: '#ffffff',
          padding: '1rem 1.25rem',
          borderRadius: '0.5rem',
          border: '1px solid #e2e8f0',
          marginBottom: '1.5rem',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>
            Event Type
          </label>
          <input
            type="text"
            placeholder="e.g. earthquake"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            style={{
              padding: '0.4rem 0.6rem',
              borderRadius: '0.375rem',
              border: '1px solid #cbd5e1',
              fontSize: '0.875rem',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>
            Region
          </label>
          <input
            type="text"
            placeholder="e.g. Pacific"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            style={{
              padding: '0.4rem 0.6rem',
              borderRadius: '0.375rem',
              border: '1px solid #cbd5e1',
              fontSize: '0.875rem',
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>
            Min Confidence: {(minConfidence * 100).toFixed(0)}%
          </label>
          <input
            type="range"
            min="0.5"
            max="0.95"
            step="0.05"
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            style={{ width: '130px' }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>
            Sort By
          </label>
          <select
            value={sortBy}
            onChange={(e) =>
              setSortBy(e.target.value as 'confidence' | 'support_count' | 'lift' | 'mined_at')
            }
            style={{
              padding: '0.4rem 0.6rem',
              borderRadius: '0.375rem',
              border: '1px solid #cbd5e1',
              fontSize: '0.875rem',
              backgroundColor: '#fff',
            }}
          >
            <option value="confidence">Confidence</option>
            <option value="lift">Statistical Lift</option>
            <option value="support_count">Support Count</option>
            <option value="mined_at">Mined Date</option>
          </select>
        </div>
      </div>

      {loading && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
          Loading research patterns...
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '1rem',
            backgroundColor: '#fef2f2',
            color: '#991b1b',
            borderRadius: '0.375rem',
            marginBottom: '1.5rem',
          }}
        >
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <PatternGraphView
            patterns={patterns}
            selectedPatternId={selectedPattern?.id ?? null}
            onSelectPattern={(p) => setSelectedPattern(p)}
          />

          {selectedPattern && (
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '0.5rem',
                padding: '1.25rem',
                marginTop: '1.5rem',
              }}
            >
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.75rem' }}>
                {`Pattern Details: ${selectedPattern.source_event_type} → ${selectedPattern.target_event_type}`}
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>Observed Rate</span>
                  <strong style={{ fontSize: '1.1rem', color: '#1e293b' }}>{(selectedPattern.observed_rate * 100).toFixed(2)}%</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>Baseline Rate</span>
                  <strong style={{ fontSize: '1.1rem', color: '#1e293b' }}>{(selectedPattern.baseline_rate * 100).toFixed(2)}%</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>Statistical Lift</span>
                  <strong style={{ fontSize: '1.1rem', color: '#047857' }}>{selectedPattern.lift.toFixed(2)}x</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', display: 'block' }}>Uncertainty Source</span>
                  <strong style={{ fontSize: '0.9rem', color: '#4338ca', textTransform: 'capitalize' }}>{selectedPattern.uncertainty.source.replace('_', ' ')}</strong>
                </div>
              </div>
              <div style={{ fontSize: '0.875rem', color: '#334155', borderTop: '1px solid #f1f5f9', paddingTop: '0.75rem' }}>
                <p><strong>Hash:</strong> <code>{selectedPattern.pattern_hash}</code> (v{selectedPattern.version}, Algo v{selectedPattern.algorithm_version})</p>
                <p><strong>Supporting Events:</strong> {selectedPattern.supporting_event_ids.length} matched event IDs</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ResearchPatternsPage;
