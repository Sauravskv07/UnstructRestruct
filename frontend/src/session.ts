const KEY = "ur-session";

export type PatientSession = {
  role: "patient";
  patientId: string;
  externalPatientId: string | null;
  name: string | null;
};

export type ClinicianSession = {
  role: "clinician";
  clinicianId: string;
  externalId: string;
  name: string;
};

export type Session = PatientSession | ClinicianSession;

export function loadSession(): Session | null {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
}

export function sessionHeaders(): Record<string, string> {
  const session = loadSession();
  if (!session) return {};
  if (session.role === "patient") {
    return { "X-App-Role": "patient", "X-Patient-Id": session.patientId };
  }
  return { "X-App-Role": "clinician", "X-Clinician-Id": session.clinicianId };
}
