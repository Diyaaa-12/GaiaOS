import { getBackups } from '../api/client';
import { ApiUnreachable } from '../components/ApiUnreachable';
import { usePoller } from '../hooks/usePoller';

const POLL_INTERVAL = Number(import.meta.env.VITE_POLL_INTERVAL_MS ?? 30_000);

const pageStyle: React.CSSProperties = {
  padding: '1.5rem',
  fontFamily: 'system-ui, sans-serif',
  color: '#1e293b',
};

function statusColor(status: string): string {
  if (status === 'SUCCESS') return '#166534';
  if (status === 'FAILED') return '#991b1b';
  return '#92400e';
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Backups page — polls GET /api/v1/admin/backups and renders backup history.
 */
export function Backups() {
  const state = usePoller(getBackups, POLL_INTERVAL);

  return (
    <main style={pageStyle}>
      <h1 style={{ fontSize: '1.4rem', marginBottom: '0.25rem' }}>Backup History</h1>

      {state.status === 'loading' && (
        <p style={{ color: '#64748b' }}>Loading backup history…</p>
      )}

      {(state.status === 'unreachable' || state.status === 'error') && (
        <ApiUnreachable error={state.lastError} intervalMs={POLL_INTERVAL} />
      )}

      {state.status === 'ok' && (
        <>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1rem' }}>
            {state.data.length} record{state.data.length !== 1 ? 's' : ''} · Last updated:{' '}
            {state.lastUpdated.toLocaleTimeString()}
          </p>

          {state.data.length === 0 ? (
            <p style={{ color: '#94a3b8' }}>No backup records found.</p>
          ) : (
            <table
              id="backups-table"
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
                  <th style={{ padding: '0.6rem' }}>Backup ID</th>
                  <th style={{ padding: '0.6rem' }}>Status</th>
                  <th style={{ padding: '0.6rem' }}>Created At</th>
                  <th style={{ padding: '0.6rem' }}>Duration</th>
                  <th style={{ padding: '0.6rem' }}>Size</th>
                  <th style={{ padding: '0.6rem' }}>Storage Location</th>
                  <th style={{ padding: '0.6rem' }}>PG Version</th>
                </tr>
              </thead>
              <tbody>
                {state.data.map((rec) => (
                  <tr key={rec.backup_id} style={{ borderTop: '1px solid #e2e8f0' }}>
                    <td
                      style={{
                        padding: '0.6rem',
                        fontFamily: 'monospace',
                        fontSize: '0.78rem',
                      }}
                    >
                      {rec.backup_id}
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      <span style={{ color: statusColor(rec.status), fontWeight: 600 }}>
                        {rec.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      {new Date(rec.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      {rec.duration_ms > 0 ? `${rec.duration_ms.toFixed(0)} ms` : '—'}
                    </td>
                    <td style={{ padding: '0.6rem' }}>{formatBytes(rec.size_bytes)}</td>
                    <td
                      style={{
                        padding: '0.6rem',
                        fontFamily: 'monospace',
                        fontSize: '0.78rem',
                        maxWidth: '200px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={rec.storage_location}
                    >
                      {rec.storage_location}
                    </td>
                    <td style={{ padding: '0.6rem' }}>{rec.postgres_version}</td>
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
