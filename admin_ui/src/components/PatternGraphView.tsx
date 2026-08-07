import React from 'react';
import type { PatternFindingResponse } from '../api/types';

interface PatternGraphViewProps {
  patterns: PatternFindingResponse[];
  selectedPatternId: string | null;
  onSelectPattern: (pattern: PatternFindingResponse) => void;
}

const containerStyle: React.CSSProperties = {
  backgroundColor: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '0.5rem',
  padding: '1.25rem',
  marginBottom: '1.5rem',
  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
};

const titleStyle: React.CSSProperties = {
  fontSize: '1.1rem',
  fontWeight: 600,
  color: '#0f172a',
  marginBottom: '0.75rem',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
};

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.2rem 0.6rem',
  borderRadius: '0.25rem',
  fontSize: '0.75rem',
  fontWeight: 600,
  backgroundColor: '#e0e7ff',
  color: '#3730a3',
};

export const PatternGraphView: React.FC<PatternGraphViewProps> = ({
  patterns,
  selectedPatternId,
  onSelectPattern,
}) => {
  if (patterns.length === 0) {
    return (
      <div style={containerStyle}>
        <div style={{ textAlign: 'center', color: '#64748b', padding: '2rem' }}>
          No longitudinal patterns found matching current criteria.
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>
        <span>Longitudinal Co-Occurrence Graph</span>
        <span style={badgeStyle}>{patterns.length} Active Patterns</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1rem',
          marginTop: '1rem',
        }}
      >
        {patterns.map((p) => {
          const isSelected = p.id === selectedPatternId;
          return (
            <div
              key={p.id}
              onClick={() => onSelectPattern(p)}
              style={{
                border: isSelected ? '2px solid #3b82f6' : '1px solid #cbd5e1',
                borderRadius: '0.375rem',
                padding: '1rem',
                backgroundColor: isSelected ? '#eff6ff' : '#f8fafc',
                cursor: 'pointer',
                transition: 'all 0.15s ease-in-out',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.5rem',
                }}
              >
                <span
                  style={{
                    fontSize: '0.875rem',
                    fontWeight: 700,
                    color: '#1e293b',
                    textTransform: 'capitalize',
                  }}
                >
                  {`${p.source_event_type} → ${p.target_event_type}`}
                </span>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: '#047857',
                    backgroundColor: '#d1fae5',
                    padding: '0.15rem 0.4rem',
                    borderRadius: '0.2rem',
                  }}
                >
                  {`${p.lift.toFixed(2)}x Lift`}
                </span>
              </div>

              <div
                style={{
                  fontSize: '0.8rem',
                  color: '#475569',
                  marginBottom: '0.75rem',
                  lineHeight: '1.4',
                }}
              >
                {p.description}
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '0.75rem',
                  color: '#64748b',
                  borderTop: '1px solid #e2e8f0',
                  paddingTop: '0.5rem',
                }}
              >
                <span>Support: {p.support_count} events</span>
                <span>Conf: {(p.statistical_confidence * 100).toFixed(1)}%</span>
                <span>Window: {p.time_window_days}d</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
