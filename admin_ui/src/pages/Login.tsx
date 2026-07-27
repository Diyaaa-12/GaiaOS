import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { login, ApiError } from '../api/client';
import { isAuthenticated } from '../utils/auth';

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '100vh',
  backgroundColor: '#0f172a',
  fontFamily: 'system-ui, sans-serif',
};

const cardStyle: React.CSSProperties = {
  background: '#1e293b',
  borderRadius: '0.75rem',
  padding: '2.5rem',
  width: '100%',
  maxWidth: '380px',
  boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.6rem 0.875rem',
  borderRadius: '0.375rem',
  border: '1px solid #334155',
  background: '#0f172a',
  color: '#f1f5f9',
  fontSize: '0.95rem',
  boxSizing: 'border-box',
  marginTop: '0.375rem',
};

const btnStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.7rem',
  borderRadius: '0.375rem',
  border: 'none',
  background: '#3b82f6',
  color: '#fff',
  fontWeight: 600,
  fontSize: '1rem',
  cursor: 'pointer',
  marginTop: '1.25rem',
};

/** Login page — authenticates against POST /api/v1/auth/login and stores the JWT.
 *  If user is already authenticated, redirects automatically to /metrics.
 */
export function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Auto-redirect if already authenticated
  if (isAuthenticated()) {
    return <Navigate to="/metrics" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/metrics');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 'unreachable') {
          setError('Cannot reach GaiaOS API. Check that the backend is running.');
        } else if (err.status === 'unauthorized') {
          setError('Invalid email or password.');
        } else {
          setError(`Login failed: ${err.message}`);
        }
      } else {
        setError('Unexpected error. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h1
          style={{
            color: '#f1f5f9',
            fontSize: '1.5rem',
            marginBottom: '0.25rem',
            textAlign: 'center',
          }}
        >
          🌍 GaiaOS Admin
        </h1>
        <p
          style={{
            color: '#94a3b8',
            fontSize: '0.85rem',
            textAlign: 'center',
            marginBottom: '1.75rem',
          }}
        >
          Sign in with your admin account
        </p>

        {error && (
          <div
            id="login-error"
            role="alert"
            style={{
              background: '#450a0a',
              color: '#fca5a5',
              border: '1px solid #7f1d1d',
              borderRadius: '0.375rem',
              padding: '0.65rem 1rem',
              marginBottom: '1rem',
              fontSize: '0.875rem',
            }}
          >
            {error}
          </div>
        )}

        <form id="login-form" onSubmit={(e) => void handleSubmit(e)} noValidate>
          <label style={{ color: '#cbd5e1', fontSize: '0.875rem' }}>
            Email
            <input
              id="input-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={inputStyle}
              placeholder="admin@gaiaos.internal"
            />
          </label>

          <label style={{ color: '#cbd5e1', fontSize: '0.875rem', display: 'block', marginTop: '1rem' }}>
            Password
            <input
              id="input-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={inputStyle}
            />
          </label>

          <button id="btn-login" type="submit" style={btnStyle} disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
