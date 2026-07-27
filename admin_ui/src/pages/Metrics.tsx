import { ApiUnreachable } from '../components/ApiUnreachable';
import { useMetrics } from '../context/MetricsContext';

const POLL_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

const pageStyle: React.CSSProperties = {
  padding: '1.5rem',
  fontFamily: 'system-ui, sans-serif',
  color: '#1e293b',
};

const cardStyle: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #e2e8f0',
  borderRadius: '0.5rem',
  padding: '1.25rem',
  marginBottom: '1.5rem',
};

/**
 * Metrics page — consumes shared MetricsContext state (single poller).
 * Displays a rollup table of p50/p95 latency and success rate per complexity tier.
 */
export function Metrics() {
  const state = useMetrics();

  return (
    <main style={pageStyle}>
      <h1 style={{ fontSize: '1.4rem', marginBottom: '0.25rem' }}>Observability Metrics</h1>

      {state.status === 'loading' && (
        <p style={{ color: '#64748b' }}>Loading metrics…</p>
      )}

      {(state.status === 'unreachable' || state.status === 'error') && (
        <ApiUnreachable error={state.lastError} intervalMs={POLL_INTERVAL} />
      )}

      {state.status === 'ok' && (
        <>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Window: <strong>{state.data.window}</strong> · Grouped by:{' '}
            <strong>{state.data.group_by}</strong> · Last updated:{' '}
            {state.lastUpdated.toLocaleTimeString()}
          </p>

          <div style={cardStyle}>
            <h2 style={{ fontSize: '1rem', marginBottom: '0.75rem', color: '#374151' }}>
              Rollups by Complexity Tier
            </h2>
            {state.data.rollups.length === 0 ? (
              <p style={{ color: '#94a3b8' }}>No metric rollups available yet.</p>
            ) : (
              <table
                id="metrics-table"
                style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}
              >
                <thead>
                  <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
                    <th style={{ padding: '0.5rem' }}>Group</th>
                    <th style={{ padding: '0.5rem' }}>Count</th>
                    <th style={{ padding: '0.5rem' }}>p50 (ms)</th>
                    <th style={{ padding: '0.5rem' }}>p95 (ms)</th>
                    <th style={{ padding: '0.5rem' }}>Success Rate</th>
                    <th style={{ padding: '0.5rem' }}>Avg Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.rollups.map((r, i) => (
                    <tr
                      key={r.group_key ?? i}
                      style={{ borderTop: '1px solid #e2e8f0' }}
                    >
                      <td style={{ padding: '0.5rem' }}>{r.group_key ?? '—'}</td>
                      <td style={{ padding: '0.5rem' }}>{r.count}</td>
                      <td style={{ padding: '0.5rem' }}>{r.p50_latency_ms.toFixed(1)}</td>
                      <td style={{ padding: '0.5rem' }}>{r.p95_latency_ms.toFixed(1)}</td>
                      <td style={{ padding: '0.5rem' }}>
                        {(r.success_rate * 100).toFixed(1)}%
                      </td>
                      <td style={{ padding: '0.5rem' }}>{r.avg_cost_estimate.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </main>
  );
}
