import { ApiUnreachable } from '../components/ApiUnreachable';
import { useMetrics } from '../context/MetricsContext';

const POLL_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

const pageStyle: React.CSSProperties = {
  padding: '1.5rem',
  fontFamily: 'system-ui, sans-serif',
  color: '#1e293b',
};

const statCardStyle: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #e2e8f0',
  borderRadius: '0.5rem',
  padding: '1.25rem 1.5rem',
  display: 'inline-flex',
  flexDirection: 'column',
  minWidth: '160px',
  marginRight: '1rem',
  marginBottom: '1rem',
};

/**
 * Workers page — consumes shared MetricsContext state (single poller).
 * Displays advisory worker scaling recommendation from GET /api/v1/admin/metrics (M7 fields).
 */
export function Workers() {
  const state = useMetrics();

  return (
    <main style={pageStyle}>
      <h1 style={{ fontSize: '1.4rem', marginBottom: '0.25rem' }}>Worker Scaling</h1>
      <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
        Advisory — informational only. No autoscaling is performed.
      </p>

      {state.status === 'loading' && (
        <p style={{ color: '#64748b' }}>Loading scaling data…</p>
      )}

      {(state.status === 'unreachable' || state.status === 'error') && (
        <ApiUnreachable error={state.lastError} intervalMs={POLL_INTERVAL} />
      )}

      {state.status === 'ok' && (
        <>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Last updated: {state.lastUpdated.toLocaleTimeString()}
          </p>

          <div id="worker-stats" style={{ display: 'flex', flexWrap: 'wrap', gap: '0' }}>
            <div style={statCardStyle}>
              <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Queue Depth
              </span>
              <span style={{ fontSize: '2rem', fontWeight: 700, color: '#1e293b', marginTop: '0.25rem' }}>
                {state.data.queue_depth}
              </span>
              <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>jobs pending</span>
            </div>

            <div style={statCardStyle}>
              <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Worker Utilisation
              </span>
              <span style={{ fontSize: '2rem', fontWeight: 700, color: '#1e293b', marginTop: '0.25rem' }}>
                {(state.data.worker_utilization_pct).toFixed(1)}%
              </span>
              <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>of pool capacity</span>
            </div>

            <div
              style={{
                ...statCardStyle,
                borderColor: '#bfdbfe',
                background: '#eff6ff',
              }}
            >
              <span style={{ fontSize: '0.78rem', color: '#3b82f6', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Recommended Pool Size
              </span>
              <span style={{ fontSize: '2rem', fontWeight: 700, color: '#1d4ed8', marginTop: '0.25rem' }}>
                {state.data.recommended_pool_size}
              </span>
              <span style={{ fontSize: '0.78rem', color: '#60a5fa' }}>workers</span>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
