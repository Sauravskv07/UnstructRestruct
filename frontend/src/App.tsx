import { type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import UploadPage from "./pages/UploadPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import RoleSelectPage from "./pages/RoleSelectPage";
import PatientGatePage from "./pages/PatientGatePage";
import ClinicianGatePage from "./pages/ClinicianGatePage";
import ClinicianHomePage from "./pages/ClinicianHomePage";
import ShareCodesPage from "./pages/ShareCodesPage";
import TimelinePage from "./pages/TimelinePage";
import { loadSession } from "./session";

function RequirePatient() {
  const session = loadSession();
  if (session?.role !== "patient") return <Navigate to="/patient" replace />;
  return <TimelinePage />;
}

function RequirePatientShare() {
  const session = loadSession();
  if (session?.role !== "patient") return <Navigate to="/patient" replace />;
  return <ShareCodesPage />;
}

function RequireClinician({ children }: { children: ReactNode }) {
  const session = loadSession();
  if (session?.role !== "clinician") return <Navigate to="/clinician/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<RoleSelectPage />} />
        <Route path="/patient" element={<PatientGatePage />} />
        <Route path="/patient/timeline" element={<RequirePatient />} />
        <Route path="/patient/share" element={<RequirePatientShare />} />
        <Route path="/clinician/login" element={<ClinicianGatePage />} />
        <Route path="/clinician" element={<Navigate to="/clinician/login" replace />} />
        <Route
          path="/clinician/patients"
          element={
            <RequireClinician>
              <ClinicianHomePage />
            </RequireClinician>
          }
        />
        <Route
          path="/clinician/patients/:id/timeline"
          element={
            <RequireClinician>
              <TimelinePage />
            </RequireClinician>
          }
        />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/query" element={<Navigate to="/clinician/patients" replace />} />
        <Route path="/patients" element={<Navigate to="/clinician/login" replace />} />
        <Route path="/patients/:id" element={<Navigate to="/clinician" replace />} />
      </Route>
    </Routes>
  );
}
