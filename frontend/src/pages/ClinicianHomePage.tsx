import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PatientSummary } from "../api";
import { loadSession } from "../session";

export default function ClinicianHomePage() {
  const session = loadSession();
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function refresh() {
    api<PatientSummary[]>("/clinician/patients")
      .then(setPatients)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const patientId = (form.elements.namedItem("patient_id") as HTMLInputElement).value.trim();
    const code = (form.elements.namedItem("code") as HTMLInputElement).value.trim();
    setError(null);
    setNotice(null);
    try {
      const added = await api<{ canonical_name: string | null }>("/clinician/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId, code }),
      });
      setNotice(`Access added for ${added.canonical_name ?? patientId}.`);
      form.reset();
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not add patient");
    }
  }

  return (
    <div>
      <h1>Patients with access</h1>
      <p className="muted">
        Signed in as {session?.role === "clinician" ? `${session.name} (${session.externalId})` : "clinician"}.
        You only see patients who shared a valid code with you.
      </p>
      <form className="card" onSubmit={onAdd}>
        <div className="grid">
          <label>
            Patient username
            <input name="patient_id" placeholder="aarav" required style={{ display: "block", width: "100%", marginTop: 6 }} />
          </label>
          <label>
            Share code
            <input name="code" placeholder="A1B2C3" required style={{ display: "block", width: "100%", marginTop: 6 }} />
          </label>
        </div>
        <button type="submit" style={{ marginTop: 12 }}>
          Add patient
        </button>
        {notice && <p className="badge">{notice}</p>}
        {error && <p className="badge err">{error}</p>}
      </form>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Phone</th>
            <th>Username</th>
            <th>Documents</th>
          </tr>
        </thead>
        <tbody>
          {patients.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No active patients yet.
              </td>
            </tr>
          )}
          {patients.map((row) => (
            <tr key={row.id}>
              <td>
                <Link to={`/clinician/patients/${row.id}/timeline`}>{row.canonical_name ?? "(unnamed)"}</Link>
              </td>
              <td>{row.phone ?? "—"}</td>
              <td>{row.username ?? "—"}</td>
              <td>
                {row.document_count} · <Link to={`/upload?patient=${row.id}`}>Upload</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
