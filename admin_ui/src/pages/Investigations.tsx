import React, { useState, useEffect, Suspense, lazy } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getInvestigationTrace, ApiError } from '../api/client';
import type { InvestigationTraceResponse } from '../api/types';
import { ApiUnreachable } from '../components/ApiUnreachable';

// Refinement 5: Lazy-load trace graph view component
const InvestigationTraceView = lazy(() =>
  import('../components/InvestigationTraceView').then((module) => ({
    default: module.InvestigationTraceView,
  })),
);

const pageStyle: React.CSSProperties = {
  padding: '1.5rem 2rem',
  maxWidth: '1200px',
  margin: '0 auto',
};

const searchBoxStyle: React.CSSProperties = {
  backgroundColor: '#ffffff',
  borderRadius: '0.5rem',
  padding: '1rem 1.25rem',
  border: '1px solid #e2e8f0',
  marginBottom: '1.5rem',
  display: 'flex',
  gap: '0.75rem',
  alignItems: 'center',
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: '0.5rem 0.75rem',
  borderRadius: '0.375rem',
  border: '1px solid #cbd5e1',
  fontSize: '0.9rem',
};

const buttonStyle: React.CSSProperties = {
  backgroundColor: '#2563eb',
  color: '#ffffff',
  border: 'none',
  borderRadius: '0.375rem',
  padding: '0.5rem 1.25rem',
  fontWeight: 600,
  fontSize: '0.85rem',
  cursor: 'pointer',
};

export function Investigations() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const [inputVal, setInputVal] = useState(id ?? '');
  const [trace, setTrace] = useState<InvestigationTraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isUnreachable, setIsUnreachable] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchTrace = async (investigationId: string) => {
    if (!investigationId.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    setIsUnreachable(false);

    try {
      const data = await getInvestigationTrace(investigationId.trim());
      setTrace(data);
    } catch (err) {
      setTrace(null);
      if (err instanceof ApiError) {
        if (err.status === 'unreachable') {
          setIsUnreachable(true);
        } else if (err.status === 'forbidden') {
          setErrorMsg('Access denied — ADMIN role required.');
        } else if (err.httpStatus === 404) {
          setErrorMsg(`Investigation ${investigationId} not found.`);
        } else {
          setErrorMsg(err.message);
        }
      } else {
        setErrorMsg('Failed to load investigation trace.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) {
      setInputVal(id);
      fetchTrace(id);
    }
  }, [id]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputVal.trim()) {
      navigate(`/investigations/${inputVal.trim()}`);
    }
  };

  return (
    <div style={pageStyle}>
      <h1 style={{ margin: '0 0 1.25rem 0', fontSize: '1.5rem', color: '#0f172a' }}>
        Investigation Reasoning Explorer
      </h1>

      <form onSubmit={handleSearchSubmit} style={searchBoxStyle}>
        <input
          type="text"
          placeholder="Enter Investigation UUID..."
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          style={inputStyle}
          id="input-investigation-id"
        />
        <button type="submit" style={buttonStyle} id="btn-fetch-trace">
          Explore Trace
        </button>
      </form>

      {isUnreachable && (
        <ApiUnreachable error={new ApiError('unreachable', undefined, 'Cannot reach GaiaOS API')} />
      )}

      {errorMsg && (
        <div
          style={{
            backgroundColor: '#fee2e2',
            color: '#991b1b',
            padding: '1rem',
            borderRadius: '0.5rem',
            border: '1px solid #fca5a5',
            marginBottom: '1.5rem',
          }}
          role="alert"
        >
          {errorMsg}
        </div>
      )}

      {loading && (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
          Loading reasoning trace graph...
        </div>
      )}

      {!loading && trace && (
        <Suspense fallback={<div style={{ padding: '1rem' }}>Rendering graph...</div>}>
          <InvestigationTraceView trace={trace} />
        </Suspense>
      )}

      {!loading && !trace && !errorMsg && !isUnreachable && (
        <div
          style={{
            backgroundColor: '#ffffff',
            borderRadius: '0.5rem',
            padding: '3rem 2rem',
            textAlign: 'center',
            border: '1px solid #e2e8f0',
            color: '#64748b',
          }}
        >
          <p style={{ margin: 0, fontSize: '1rem' }}>
            Enter an Investigation ID above to visualize its complete execution reasoning trace.
          </p>
        </div>
      )}
    </div>
  );
}
