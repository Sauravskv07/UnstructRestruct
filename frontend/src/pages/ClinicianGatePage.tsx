import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import PasswordField from "../components/PasswordField";
import { saveSession } from "../session";

export default function ClinicianGatePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const clinicianId = (form.elements.namedItem("clinician_id") as HTMLInputElement).value.trim();
    const password = (form.elements.namedItem("password") as HTMLInputElement).value;
    setError(null);
    try {
      const result = await api<{
        clinician_id: string;
        external_id: string;
        name: string;
      }>("/auth/clinician", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clinician_id: clinicianId, password }),
      });
      saveSession({
        role: "clinician",
        clinicianId: result.clinician_id,
        externalId: result.external_id,
        name: result.name,
      });
      navigate("/clinician/patients");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not sign in");
    }
  }

  return (
    <div>
      <h1>Healthcare professional</h1>
      <p className="muted">
        Enter a clinician ID. If it is new, we create an account with this password.
        The seeded demo account is <code>DOC-1001</code> with password <code>demo</code>.
      </p>
      <form className="card" onSubmit={onSubmit}>
        <label>
          Clinician ID
          <input name="clinician_id" placeholder="DOC-1001" required style={{ display: "block", width: "100%", margin: "6px 0 12px" }} />
        </label>
        <label>
          Password
          <PasswordField name="password" defaultValue="demo" required />
        </label>
        <button type="submit">Continue</button>
        {error && <p className="badge err">{error}</p>}
      </form>
    </div>
  );
}
