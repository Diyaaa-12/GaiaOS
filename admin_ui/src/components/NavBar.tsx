import { NavLink, useNavigate } from 'react-router-dom';
import { logout } from '../api/client';

const navStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '1.5rem',
  padding: '0.75rem 1.5rem',
  backgroundColor: '#1e293b',
  color: '#f1f5f9',
  fontFamily: 'system-ui, sans-serif',
  fontSize: '0.9rem',
};

const linkStyle: React.CSSProperties = {
  color: '#94a3b8',
  textDecoration: 'none',
};

const activeLinkStyle: React.CSSProperties = {
  color: '#f8fafc',
  fontWeight: 600,
  borderBottom: '2px solid #3b82f6',
  paddingBottom: '0.2rem',
};

/** Top navigation bar — links to all admin dashboard pages using NavLink for active styling. */
export function NavBar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getStyle = ({ isActive }: { isActive: boolean }) =>
    isActive ? { ...linkStyle, ...activeLinkStyle } : linkStyle;

  return (
    <nav style={navStyle} aria-label="Admin navigation">
      <span style={{ fontWeight: 700, fontSize: '1rem', color: '#f1f5f9', marginRight: '1rem' }}>
        🌍 GaiaOS Admin
      </span>
      <NavLink to="/metrics" style={getStyle} id="nav-metrics">
        Metrics
      </NavLink>
      <NavLink to="/alerts" style={getStyle} id="nav-alerts">
        Alerts
      </NavLink>
      <NavLink to="/workers" style={getStyle} id="nav-workers">
        Workers
      </NavLink>
      <NavLink to="/backups" style={getStyle} id="nav-backups">
        Backups
      </NavLink>
      <span style={{ marginLeft: 'auto' }}>
        <button
          id="btn-logout"
          onClick={handleLogout}
          style={{
            background: 'none',
            border: '1px solid #475569',
            color: '#94a3b8',
            borderRadius: '0.25rem',
            padding: '0.25rem 0.75rem',
            cursor: 'pointer',
            fontSize: '0.85rem',
          }}
        >
          Log out
        </button>
      </span>
      <style>{`
        nav a:hover { color: #f8fafc !important; }
      `}</style>
    </nav>
  );
}
