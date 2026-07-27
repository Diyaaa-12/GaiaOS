import { getAlerts } from '../api/client';
import { ApiUnreachable } from '../components/ApiUnreachable';
import { usePoller } from '../hooks/usePoller';
import type { AlertIncidentResponse } from '../api/types';

const POLL_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

const pageStyle: React.CSSProperties = {
  padding: '1.5rem',
  fontFamily: 'system-ui, sans-serif',
  color: '#1e293b',
};

function StatusBadge({ status }: { status: AlertIncidentResponse['status'] }) {
  const isFiring = status === 'firing';
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.2rem 0.6rem',
        borderRadius: '9999px',
        fontSize: '0.78rem',
        fontWeight: 600,
        background: isFiring ? '#fee2e2' : '#dcfce7',
        color: isFiring ? '#991b1b' : '#166534',
        border: `1px solid ${isFiring ? '#fca5a5' : '#86efac'}`,
      }}
    >
      {isFiring ? '🔴 Firing' : '✅ Resolved'}
    </span>
  );
}

/**
 * Alerts page — polls GET /api/v1/admin/alerts and renders incident list
 * with firing/resolved status badges.
 */
export function Alerts() {
  const state = usePoller(getAlerts, POLL_INTERVAL);

  return (
    <main style={pageStyle}>
      <h1 style={{ fontSize: '1.4rem', marginBottom: '0.25rem' }}>Alert Incidents</h1>

      {state.status === 'loading' && (
        <p style={{ color: '#64748b' }}>Loading alerts…</p>
      )}

      {(state.status === 'unreachable' || state.status === 'error') && (
        <ApiUnreachable error={state.lastError} intervalMs={POLL_INTERVAL} />
      )}

      {state.status === 'ok' && (
        <>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1rem' }}>
            {state.data.length} incident{state.data.length !== 1 ? 's' : ''} · Last updated:{' '}
            {state.lastUpdated.toLocaleTimeString()}
          </p>

          {state.data.length === 0 ? (
            <p style={{ color: '#94a3b8' }}>No alert incidents found.</p>
          ) : (
            <table
              id="alerts-table"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.875rem',
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '0.5rem',
              }}
            >
              <thead>
                <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
                  <th style={{ padding: '0.6rem' }}>Status</th>
                  <th style={{ padding: '0.6rem' }}>Rule</th>
                  <th style={{ padding: '0.6rem' }}>Severity</th>
                  <th style={{ padding: '0.6rem' }}>Last Value</th>
                  <th style={{ padding: '0.6rem' }}>Threshold</th>
                  <th style={{ padding: '0.6rem' }}>Violations</th>
                  <th style={{ padding: '0.6rem' }}>Fired At</th>
                  <th style={{ padding: '0.6rem' }}>Resolved At</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((inc) => (
                  <tr key={inc.id} style={{ borderTop: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '0.6rem' }}>
                      <StatusBadge status={inc.status} />
                    </td>
                    <td style={{ padding: '0.6rem', fontWeight: 500 }}>{inc.rule_name}</td>
                    <td style={{ padding: '0.6rem', textTransform: 'capitalize' }}>{inc.severity}</td>
                    <td style={{ padding: '0.6rem' }}>{inc.last_value.toFixed(3)}</td>
                    <td style={{ padding: '0.6rem' }}>{inc.threshold.toFixed(3)}</td>
                    <td style={{ padding: '0.6rem' }}>{inc.consecutive_violations}</td>
                    <td style={{ padding: '0.6rem' }}>
                      {new Date(inc.fired_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      {inc.resolved_at ? new Date(inc.resolved_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </main>
  );
}
