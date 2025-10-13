import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import FullPageLoader from "../components/FullPageLoader";

const ProtectedRoute = () => {
  const location = useLocation();
  const { isAuthenticated, status, statusMessage } = useAuth();

  if (status === "checking" || status === "authenticating") {
    return <FullPageLoader message={statusMessage ?? "Signing you in…"} />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
