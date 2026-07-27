import { Navigate, Outlet, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { MetricsProvider } from './context/MetricsContext';
import { Alerts } from './pages/Alerts';
import { Backups } from './pages/Backups';
import { Login } from './pages/Login';
import { Metrics } from './pages/Metrics';
import { Workers } from './pages/Workers';
import { isAuthenticated } from './utils/auth';

const appStyle: React.CSSProperties = {
  minHeight: '100vh',
  backgroundColor: '#f8fafc',
};

/** Protected layout route — returns a single JSX root wrapping child routes in MetricsProvider + NavBar + Outlet when authenticated. */
function ProtectedLayout() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return (
    <MetricsProvider>
      <div style={appStyle}>
        <NavBar />
        <Outlet />
      </div>
    </MetricsProvider>
  );
}

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Public login route */}
        <Route path="/login" element={<Login />} />

        {/* Protected admin layout and child routes */}
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Navigate to="/metrics" replace />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/workers" element={<Workers />} />
          <Route path="/backups" element={<Backups />} />
        </Route>
      </Routes>
    </Router>
  );
}
