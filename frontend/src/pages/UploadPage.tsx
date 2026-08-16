import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, DocumentSummary, isInFlight, PatientSummary, uploadDocument } from "../api";
import DocumentsList from "../components/DocumentsList";
import { loadSession } from "../session";

export default function UploadPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [rows, setRows] = useState<DocumentSummary[]>([]);
  const [pickerKey, setPickerKey] = useState(0);
  const [params] = useSearchParams();
  const session = loadSession();
  const preselected = params.get("patient") ?? "";

  function loadDocuments() {
    return api<DocumentSummary[]>("/documents")
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    if (session?.role === "clinician") {
      api<PatientSummary[]>("/clinician/patients")
        .then(setPatients)
        .catch((err: Error) => setError(err.message));
    }
    void loadDocuments();
  }, [session?.role]);

  useEffect(() => {
    if (!rows.some((row) => isInFlight(row.status))) return undefined;
    const timer = window.setInterval(() => {
      void loadDocuments();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [rows]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const target =
      session?.role === "clinician"
        ? (form.elements.namedItem("target_patient_id") as HTMLSelectElement).value
        : undefined;
    if (session?.role === "clinician" && !target) {
      setError("Select a patient you have access to.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const accepted = await uploadDocument(file, target);
      setNotice(`${accepted.filename} is processing. You can upload another file.`);
      setPickerKey((value) => value + 1);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Upload document</h1>
      <p className="muted">
        The file is queued immediately. Confirm it from the list when processing finishes. You can keep uploading while others run.
      </p>
      <form className="card" onSubmit={onSubmit}>
        {session?.role === "clinician" && (
          <label style={{ display: "block", marginBottom: 14 }}>
            Patient
            <select name="target_patient_id" defaultValue={preselected} required style={{ display: "block", width: "100%", marginTop: 8 }}>
              <option value="">Select a patient</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.canonical_name ?? "unnamed"}
                  {p.phone ? ` · ${p.phone}` : ""}
                  {p.username ? ` (${p.username})` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        <FilePicker key={pickerKey} />
        <div className="upload-actions">
          <button type="submit" disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </div>
        {notice && <p className="badge">{notice}</p>}
        {error && <p className="badge err">{error}</p>}
      </form>
      <h2 style={{ fontSize: "1.1rem", marginTop: 28 }}>Your documents</h2>
      <DocumentsList rows={rows} />
    </div>
  );
}

function FilePicker() {
  const [name, setName] = useState("PDF or image — no file chosen");
  return (
    <label className="file-picker">
      <input
        name="file"
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp"
        required
        onChange={(event) => {
          const file = event.target.files?.[0];
          setName(file ? file.name : "PDF or image — no file chosen");
        }}
      />
      <span className="file-picker-btn">Choose file</span>
      <span className="file-picker-name">{name}</span>
    </label>
  );
}
