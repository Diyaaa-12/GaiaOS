/**
 * Thin, manually-maintained typed API client for the GaiaOS admin HTTP surface.
 *
 * Design principles:
 * - No code generation. Typed against src/api/types.ts.
 * - All network failures throw ApiError with status 'unreachable' so callers
 *   can render a consistent graceful-failure state.
 * - JWT is read from localStorage on every call — no module-level caching
 *   so token refreshes (e.g., after re-login) take effect immediately.
 */

import { AUTH_TOKEN_KEY } from '../utils/auth';
import type {
  AlertIncidentResponse,
  BackupRecordSchema,
  MetricsResponse,
  TokenResponse,
} from './types';

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export type ApiErrorStatus = 'unreachable' | 'unauthorized' | 'forbidden' | 'server_error' | 'unknown';

export class ApiError extends Error {
  constructor(
    public readonly status: ApiErrorStatus,
    public readonly httpStatus?: number,
    message?: string,
  ) {
    super(message ?? `API error: ${status}`);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...init?.headers,
      },
    });
  } catch {
    // Network-level failure (DNS, refused connection, timeout)
    throw new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API');
  }

  if (response.status === 401) {
    logout();
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new ApiError('unauthorized', 401, 'Unauthorized — please log in again');
  }
  if (response.status === 403) {
    throw new ApiError('forbidden', 403, 'Forbidden — ADMIN role required');
  }
  if (!response.ok) {
    throw new ApiError('server_error', response.status, `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

/**
 * Authenticate with the GaiaOS backend and store the JWT in localStorage.
 * Returns the raw token string on success.
 */
export async function login(email: string, password: string): Promise<string> {
  const data = await request<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
  return data.access_token;
}

/** Remove the stored JWT (client-side logout). */
export function logout(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

/** Fetch aggregated metrics + worker scaling data. */
export async function getMetrics(window = '7d'): Promise<MetricsResponse> {
  return request<MetricsResponse>(`/api/v1/admin/metrics?window=${window}`);
}

/** Fetch alert incidents with optional status filter. */
export async function getAlerts(
  status?: 'firing' | 'resolved',
): Promise<AlertIncidentResponse[]> {
  const qs = status ? `?status=${status}` : '';
  return request<AlertIncidentResponse[]>(`/api/v1/admin/alerts${qs}`);
}

/** Fetch backup history records. */
export async function getBackups(limit = 50): Promise<BackupRecordSchema[]> {
  return request<BackupRecordSchema[]>(`/api/v1/admin/backups?limit=${limit}`);
}
