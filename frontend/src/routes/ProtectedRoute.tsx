import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import FullPageLoader from '../components/FullPageLoader';

const ProtectedRoute = () => {
  const location = useLocation();
  const { isAuthenticated, status, statusMessage } = useAuth();
  const hasStoredAuth =
    typeof window !== 'undefined' && Boolean(window.localStorage.getItem('adinsights.auth'));

  // OAuth callback guard: if the URL carries ?code=&state=, the user just returned
  // from an OAuth consent screen. NEVER redirect to /login in this window — the
  // Navigate would strip the code/state from the URL and the DataSources callback
  // handler would never get a chance to exchange the code for a token.
  const hasOAuthCallback =
    typeof window !== 'undefined' &&
    (() => {
      const params = new URLSearchParams(window.location.search);
      return (
        (params.has('code') && params.has('state')) ||
        params.has('error') ||
        params.has('error_reason')
      );
    })();

  if (isAuthenticated || (status === 'idle' && hasStoredAuth)) {
    return <Outlet />;
  }

  if (status === 'checking' || status === 'authenticating') {
    return <FullPageLoader message={statusMessage ?? 'Signing you in…'} />;
  }

  if (hasOAuthCallback && hasStoredAuth) {
    // Auth is resolving; give DataSources the chance to consume the OAuth params.
    return <FullPageLoader message="Completing OAuth…" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
};

export default ProtectedRoute;
