import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import PasswordField from "../components/PasswordField";
import { saveSession } from "../session";

export default function PatientGatePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const username = (form.elements.namedItem("username") as HTMLInputElement).value.trim();
    const password = (form.elements.namedItem("password") as HTMLInputElement).value;
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    const phone = (form.elements.namedItem("phone") as HTMLInputElement).value.trim();
    setError(null);
    try {
      const result = await api<{
        patient_id: string;
        username: string | null;
        external_patient_id: string | null;
        canonical_name: string | null;
        phone: string | null;
      }>("/auth/patient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, name: name || null, phone: phone || null }),
      });
      saveSession({
        role: "patient",
        patientId: result.patient_id,
        externalPatientId: result.external_patient_id,
        name: result.canonical_name,
      });
      navigate("/patient/timeline");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not sign in");
    }
  }

  return (
    <div>
      <h1>Patient</h1>
      <p className="muted">
        Username is only for signing in. You are identified by name and phone.
        If this username is new, we create an account with this password. Existing charts such as{" "}
        <code>PAT-1001</code> still use <code>demo</code> until they have their own password.
      </p>
      <form className="card" onSubmit={onSubmit}>
        <label>
          Username
          <input name="username" placeholder="aarav" required style={{ display: "block", width: "100%", margin: "6px 0 12px" }} />
        </label>
        <label>
          Password
          <PasswordField name="password" defaultValue="demo" required />
        </label>
        <label>
          Full name
          <input name="name" placeholder="used when creating a new account" style={{ display: "block", width: "100%", margin: "6px 0 12px" }} />
        </label>
        <label>
          Phone
          <input name="phone" placeholder="used when creating a new account" style={{ display: "block", width: "100%", margin: "6px 0 12px" }} />
        </label>
        <button type="submit">View my records</button>
        {error && <p className="badge err">{error}</p>}
      </form>
    </div>
  );
}
