import { Navigate, Outlet, useLocation } from "react-router-dom";

export default function AdminGate() {
  const location = useLocation();
  if (!localStorage.getItem("reviewer_token")) {
    return <Navigate to="/admin/access" state={{ from: location.pathname }} replace />;
  }
  return <Outlet />;
}