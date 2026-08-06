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

// ---------------------------------------------------------------------------
// Explainability Trace (GET /api/v1/investigations/{id}/trace)
// ---------------------------------------------------------------------------

export interface TraceNode {
  id: string;
  label: string;
  type: string; // planning | agent_started | synthesizing | critic_flag | replanning | collaboration | finalize | custom
  status: string; // completed | failed | skipped | flagged | degraded
  timestamp?: string | null;
  details?: Record<string, unknown>;
}

export interface TraceEdge {
  id: string;
  source: string;
  target: string;
  label?: string | null;
  type?: string | null; // sequential | replan | collaboration | conditional
}

export interface TraceSummary {
  evidence_count: number;
  replan_count: number;
  critic_flag_count: number;
  collaboration_event_count: number;
  degraded_sources: string[];
}

export interface TraceMetadata {
  investigation_id: string;
  schema_version: string;
  generated_at: string; // ISO 8601
  status: string;
  complexity_tier?: string | null;
  created_at: string;
  completed_at?: string | null;
  confidence?: number | null;
  node_count: number;
  edge_count: number;
  has_replan: boolean;
  has_collaboration: boolean;
  has_degraded_mode: boolean;
}

export interface InvestigationTraceResponse {
  investigation_id: string;
  schema_version: string;
  metadata: TraceMetadata;
  nodes: TraceNode[];
  edges: TraceEdge[];
  summary: TraceSummary;
}

export interface InvestigationStatusResponse {
  investigation_id: string;
  status: string;
  complexity_tier?: string | null;
  answer?: string | null;
  confidence?: number | null;
  evidence_gaps: string[];
  execution_trace?: Record<string, unknown> | null;
  created_at: string;
  completed_at?: string | null;
}

