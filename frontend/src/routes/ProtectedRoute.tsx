import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import FullPageLoader from '../components/FullPageLoader';

const ProtectedRoute = () => {
  const location = useLocation();
  const { isAuthenticated, status, statusMessage } = useAuth();
  const hasStoredAuth =
    typeof window !== 'undefined' && Boolean(window.localStorage.getItem('adinsights.auth'));

  if (isAuthenticated || (status === 'idle' && hasStoredAuth)) {
    return <Outlet />;
  }

  if (status === 'checking' || status === 'authenticating') {
    return <FullPageLoader message={statusMessage ?? 'Signing you in…'} />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
};

export default ProtectedRoute;
