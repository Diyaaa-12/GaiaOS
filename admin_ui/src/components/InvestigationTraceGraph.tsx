import React from 'react';
import type { TraceEdge, TraceNode } from '../api/types';

interface InvestigationTraceGraphProps {
  nodes: TraceNode[];
  edges: TraceEdge[];
  selectedNodeId: string | null;
  onSelectNode: (node: TraceNode) => void;
}

const badgeBaseStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.2rem 0.55rem',
  borderRadius: '0.25rem',
  fontSize: '0.75rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.025em',
};

function getTypeBadgeStyle(type: string): React.CSSProperties {
  switch (type) {
    case 'planning':
    case 'supervisor':
      return { ...badgeBaseStyle, backgroundColor: '#e0e7ff', color: '#3730a3' };
    case 'agent_started':
      return { ...badgeBaseStyle, backgroundColor: '#dbeafe', color: '#1e40af' };
    case 'synthesizing':
      return { ...badgeBaseStyle, backgroundColor: '#f3e8ff', color: '#6b21a8' };
    case 'critic_flag':
      return { ...badgeBaseStyle, backgroundColor: '#fef3c7', color: '#92400e' };
    case 'replanning':
      return { ...badgeBaseStyle, backgroundColor: '#ffedd5', color: '#9a3412' };
    case 'collaboration':
      return { ...badgeBaseStyle, backgroundColor: '#ccfbf1', color: '#115e59' };
    case 'finalize':
      return { ...badgeBaseStyle, backgroundColor: '#dcfce7', color: '#166534' };
    default:
      return { ...badgeBaseStyle, backgroundColor: '#f1f5f9', color: '#475569' };
  }
}

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

/**
 * Isolated Graph Visualizer Component (Refinement 4).
 * Encapsulates node rendering and edge visual transitions independently from the container page.
 */
export function InvestigationTraceGraph({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
}: InvestigationTraceGraphProps) {
  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        borderRadius: '0.5rem',
        padding: '1.5rem',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}
      data-testid="investigation-trace-graph"
    >
      <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', color: '#1e293b' }}>
        Reasoning Path Graph ({nodes.length} Nodes, {edges.length} Edges)
      </h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {nodes.map((node, index) => {
          const isSelected = selectedNodeId === node.id;
          return (
            <React.Fragment key={node.id}>
              <div
                onClick={() => onSelectNode(node)}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: '0.5rem',
                  border: isSelected ? '2px solid #3b82f6' : '1px solid #cbd5e1',
                  backgroundColor: isSelected ? '#eff6ff' : '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
                role="button"
                tabIndex={0}
                aria-label={`Node ${node.label}`}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#0f172a' }}>
                    {node.label}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                    ID: {node.id}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  <span style={getTypeBadgeStyle(node.type)}>{node.type}</span>
                  <span style={getStatusBadgeStyle(node.status)}>{node.status}</span>
                </div>
              </div>

              {index < nodes.length - 1 && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '1.2rem',
                    color: '#94a3b8',
                    fontSize: '0.85rem',
                  }}
                >
                  ↓
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
