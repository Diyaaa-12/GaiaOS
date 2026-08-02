/**
 * Typed API interfaces mirroring GaiaOS backend Pydantic response schemas.
 *
 * Manually maintained — kept in sync with:
 *   app/api/v1/auth.py          → TokenResponse
 *   app/api/v1/admin_metrics.py → MetricsResponse, MetricRollupSchema
 *   app/api/v1/admin_alerts.py  → AlertIncidentResponse
 *   app/api/v1/admin_backups.py → BackupRecordSchema
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

// ---------------------------------------------------------------------------
// Metrics (GET /api/v1/admin/metrics)
// ---------------------------------------------------------------------------

export interface MetricRollupSchema {
  group_key: string | null;
  count: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  avg_cost_estimate: number;
  success_rate: number;
}

export interface MetricsResponse {
  window: string;
  group_by: string;
  rollups: MetricRollupSchema[];
  queue_depth: number;
  worker_utilization_pct: number;
  recommended_pool_size: number;
}

// ---------------------------------------------------------------------------
// Alerts (GET /api/v1/admin/alerts)
// ---------------------------------------------------------------------------

export interface AlertIncidentResponse {
  id: string;
  rule_id: string | null;
  rule_name: string;
  slo_name?: string | null;
  severity: string;
  status: 'firing' | 'resolved';
  last_value: number;
  threshold: number;
  consecutive_violations: number;
  fired_at: string;   // ISO 8601
  resolved_at: string | null;
}

// ---------------------------------------------------------------------------
// Backups (GET /api/v1/admin/backups)
// ---------------------------------------------------------------------------

export interface BackupRecordSchema {
  backup_id: string;
  created_at: string;       // ISO 8601
  completed_at: string | null;
  status: string;
  size_bytes: number;
  checksum: string;
  storage_location: string;
  postgres_version: string;
  duration_ms: number;
  verification_metadata: Record<string, unknown>;
  error_details: string | null;
}
