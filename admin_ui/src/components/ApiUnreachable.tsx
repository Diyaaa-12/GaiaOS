import type { ApiError } from '../api/client';

interface ApiUnreachableProps {
  error: ApiError;
  intervalMs?: number;
}

/**
 * Graceful-failure banner displayed when the GaiaOS API cannot be reached.
 * Shown instead of a blank page or unhandled exception — per Milestone 9 §17.
 */
export function ApiUnreachable({ error, intervalMs = 30_000 }: ApiUnreachableProps) {
  const intervalSec = Math.round(intervalMs / 1000);
  const isUnreachable = error.status === 'unreachable';

  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '1rem 1.25rem',
        borderRadius: '0.5rem',
        backgroundColor: isUnreachable ? '#fff3cd' : '#f8d7da',
        border: `1px solid ${isUnreachable ? '#ffc107' : '#f5c2c7'}`,
        color: isUnreachable ? '#664d03' : '#842029',
        fontFamily: 'system-ui, sans-serif',
        fontSize: '0.9rem',
        margin: '1rem 0',
      }}
    >
      <span aria-hidden="true" style={{ fontSize: '1.25rem' }}>
        {isUnreachable ? '⚠' : '✕'}
      </span>
      <div>
        <strong>
          {isUnreachable
            ? 'Cannot reach GaiaOS API'
            : `API error (HTTP ${error.httpStatus ?? 'unknown'})`}
        </strong>
        <div style={{ marginTop: '0.25rem', opacity: 0.85 }}>
          {isUnreachable
            ? `Retrying every ${intervalSec}s. Check that the backend is running.`
            : error.message}
        </div>
      </div>
    </div>
  );
}
