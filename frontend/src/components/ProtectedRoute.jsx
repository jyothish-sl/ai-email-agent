import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, initializing } = useAuth();

  if (initializing) {
    return <div className="loading-state">Loading your session…</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return children;
}
