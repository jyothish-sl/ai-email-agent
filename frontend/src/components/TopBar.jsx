import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
    navigate("/");
  }

  return (
    <div className="topbar">
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        <div className="brand">
          <span className="brand-mark" />
          <span className="brand-name">EMAIL AGENT</span>
        </div>
        <nav style={{ display: "flex", gap: 4 }}>
          <NavLink to="/dashboard" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Dashboard
          </NavLink>
          <NavLink to="/emails" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Emails
          </NavLink>
          <NavLink to="/schedules" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Schedules
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            Settings
          </NavLink>
        </nav>
      </div>
      <div className="topbar-right">
        {user && (
          <span className="user-chip">
            <strong>{user.username}</strong> · {user.email}
          </span>
        )}
        <button className="btn-ghost" onClick={handleLogout} disabled={loggingOut}>
          {loggingOut ? "Logging out…" : "Log out"}
        </button>
      </div>
    </div>
  );
}
