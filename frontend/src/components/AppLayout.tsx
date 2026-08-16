import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import NetworkBackdrop from "./NetworkBackdrop";
import { clearSession, loadSession } from "../session";

export default function AppLayout() {
  const session = loadSession();
  const location = useLocation();

  if (!session && !["/", "/patient", "/clinician", "/clinician/login"].includes(location.pathname)) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="layout">
      <NetworkBackdrop />
      <nav>
        <Link to="/">Role</Link>
        {session?.role === "patient" && (
          <>
            <NavLink to="/patient/timeline">Timeline</NavLink>
            <NavLink to="/patient/share">Share access</NavLink>
            <NavLink to="/upload">Upload</NavLink>
            <NavLink to="/documents">Documents</NavLink>
          </>
        )}
        {session?.role === "clinician" && (
          <>
            <NavLink to="/clinician/patients">Patients</NavLink>
            <NavLink to="/upload">Upload</NavLink>
            <NavLink to="/documents">Documents</NavLink>
          </>
        )}
        {session && (
          <button type="button" className="secondary nav-switch" onClick={() => { clearSession(); window.location.href = "/"; }}>
            Switch role
          </button>
        )}
      </nav>
      <Outlet />
    </div>
  );
}
