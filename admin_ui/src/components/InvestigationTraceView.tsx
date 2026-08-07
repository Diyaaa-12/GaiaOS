import React, { useState } from 'react';
import type { InvestigationTraceResponse, TraceNode } from '../api/types';
import { InvestigationTraceGraph } from './InvestigationTraceGraph';

interface TraceViewProps {
  trace: InvestigationTraceResponse;
}

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '1.5rem',
  fontFamily: 'system-ui, -apple-system, sans-serif',
};

const headerCardStyle: React.CSSProperties = {
  backgroundColor: '#ffffff',
  borderRadius: '0.5rem',
  padding: '1.25rem 1.5rem',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  border: '1px solid #e2e8f0',
};

const badgeBaseStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.2rem 0.55rem',
  borderRadius: '0.25rem',
  fontSize: '0.75rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.025em',
};

function getStatusBadgeStyle(status: string): React.CSSProperties {
  switch (status) {
    case 'completed':
      return { ...badgeBaseStyle, backgroundColor: '#d1fae5', color: '#065f46' };
    case 'flagged':
      return { ...badgeBaseStyle, backgroundColor: '#fef3c7', color: '#92400e' };
    case 'degraded':
      return { ...badgeBaseStyle, backgroundColor: '#ffe4e6', color: '#9f1239' };
    case 'failed':
      return { ...badgeBaseStyle, backgroundColor: '#fee2e2', color: '#991b1b' };
    default:
      return { ...badgeBaseStyle, backgroundColor: '#f1f5f9', color: '#475569' };
  }
}

export function InvestigationTraceView({ trace }: TraceViewProps) {
  const [selectedNode, setSelectedNode] = useState<TraceNode | null>(
    trace.nodes.length > 0 ? trace.nodes[0] : null,
  );

  const { metadata, nodes, edges, summary } = trace;

  return (
    <div style={containerStyle} data-testid="investigation-trace-view">
      {/* Header Metadata Summary */}
      <div style={headerCardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#0f172a' }}>
              Execution Reasoning Trace
            </h2>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Investigation ID: {metadata.investigation_id}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569', backgroundColor: '#f1f5f9', padding: '0.2rem 0.5rem', borderRadius: '0.25rem' }}>
              Schema v{metadata.schema_version}
            </span>
            <span style={getStatusBadgeStyle(metadata.status)}>{metadata.status}</span>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.25rem', fontSize: '0.85rem', color: '#334155' }}>
          <div>
            <strong>Tier:</strong> {metadata.complexity_tier ?? 'N/A'}
          </div>
          <div>
            <strong>Confidence:</strong>{' '}
            {metadata.confidence !== null && metadata.confidence !== undefined
              ? `${(metadata.confidence * 100).toFixed(1)}%`
              : 'N/A'}
          </div>
          <div>
            <strong>Evidence Items:</strong> {summary.evidence_count}
          </div>
          <div>
            <strong>Generated At:</strong> {new Date(metadata.generated_at).toLocaleTimeString()}
          </div>
        </div>

        {/* Feature Tags */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
          {metadata.has_replan && (
            <span style={{ ...badgeBaseStyle, backgroundColor: '#ffedd5', color: '#9a3412' }}>
              🔄 Targeted Replan Pass ({summary.replan_count})
            </span>
          )}
          {metadata.has_collaboration && (
            <span style={{ ...badgeBaseStyle, backgroundColor: '#ccfbf1', color: '#115e59' }}>
              🤝 Agent Collaboration ({summary.collaboration_event_count})
            </span>
          )}
          {metadata.has_degraded_mode && (
            <span style={{ ...badgeBaseStyle, backgroundColor: '#ffe4e6', color: '#9f1239' }}>
              ⚠️ Degraded Mode ({summary.degraded_sources.join(', ')})
            </span>
          )}
        </div>
      </div>

      {/* Main Interactive Graph & Details Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem' }}>
        {/* Isolated Graph Renderer */}
        <InvestigationTraceGraph
          nodes={nodes}
          edges={edges}
          selectedNodeId={selectedNode?.id ?? null}
          onSelectNode={(n) => setSelectedNode(n)}
        />

        {/* Selected Node Details Drawer */}
        <div
          style={{
            backgroundColor: '#ffffff',
            borderRadius: '0.5rem',
            padding: '1.25rem',
            border: '1px solid #e2e8f0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            alignSelf: 'start',
          }}
        >
          <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', color: '#1e293b' }}>
            Node Inspection Panel
          </h3>

          {selectedNode ? (
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a', marginBottom: '0.5rem' }}>
                {selectedNode.label}
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1rem' }}>
                <span style={getStatusBadgeStyle(selectedNode.status)}>{selectedNode.status}</span>
              </div>

              {selectedNode.details && Object.keys(selectedNode.details).length > 0 ? (
                <div>
                  <h4 style={{ margin: '0.75rem 0 0.4rem 0', fontSize: '0.85rem', color: '#475569' }}>
                    Execution Details:
                  </h4>
                  <pre
                    style={{
                      backgroundColor: '#f1f5f9',
                      padding: '0.75rem',
                      borderRadius: '0.375rem',
                      fontSize: '0.75rem',
                      overflowX: 'auto',
                      color: '#1e293b',
                    }}
                  >
                    {JSON.stringify(selectedNode.details, null, 2)}
                  </pre>
                </div>
              ) : (
                <p style={{ fontSize: '0.8rem', color: '#64748b' }}>No extra payload for this step.</p>
              )}
            </div>
          ) : (
            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>Select a node to inspect details.</p>
          )}
        </div>
      </div>
    </div>
  );
}
