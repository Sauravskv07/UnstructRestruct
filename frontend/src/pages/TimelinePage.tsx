import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  ChartCatalog,
  DiagnosticQueryRow,
  LabQueryRow,
  MedQueryRow,
  PatientDetail,
} from "../api";
import ClusteredTimeline from "../components/ClusteredTimeline";
import { loadSession } from "../session";

type Mode = "timeline" | "lab" | "medication" | "diagnostic";

export default function TimelinePage() {
  const { id } = useParams();
  const session = loadSession();
  const patientId = id ?? (session?.role === "patient" ? session.patientId : undefined);
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [catalog, setCatalog] = useState<ChartCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("timeline");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [test, setTest] = useState("");
  const [med, setMed] = useState("");
  const [study, setStudy] = useState("");
  const [labs, setLabs] = useState<LabQueryRow[] | null>(null);
  const [meds, setMeds] = useState<MedQueryRow[] | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticQueryRow[] | null>(null);

  useEffect(() => {
    if (!patientId) {
      setError("No patient selected.");
      return;
    }
    api<ChartCatalog>(`/patients/${patientId}/catalog`)
      .then(setCatalog)
      .catch((err: Error) => setError(err.message));
  }, [patientId]);

  useEffect(() => {
    if (!patientId || mode !== "timeline") return;
    const params = new URLSearchParams();
    if (dateFrom) params.set("from", dateFrom);
    if (dateTo) params.set("to", dateTo);
    const query = params.toString();
    api<PatientDetail>(`/patients/${patientId}${query ? `?${query}` : ""}`)
      .then(setPatient)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, dateFrom, dateTo]);

  useEffect(() => {
    if (!patientId || mode !== "lab" || !test) {
      if (mode !== "lab") setLabs(null);
      return;
    }
    const params = new URLSearchParams({ test });
    api<LabQueryRow[]>(`/patients/${patientId}/lab-results?${params}`)
      .then(setLabs)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, test]);

  useEffect(() => {
    if (!patientId || mode !== "medication" || !med) {
      if (mode !== "medication") setMeds(null);
      return;
    }
    const params = new URLSearchParams({ name: med });
    api<MedQueryRow[]>(`/patients/${patientId}/medications?${params}`)
      .then(setMeds)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, med]);

  useEffect(() => {
    if (!patientId || mode !== "diagnostic" || !study) {
      if (mode !== "diagnostic") setDiagnostics(null);
      return;
    }
    const params = new URLSearchParams({ study });
    api<DiagnosticQueryRow[]>(`/patients/${patientId}/diagnostics?${params}`)
      .then(setDiagnostics)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, study]);

  function onModeChange(next: Mode) {
    setMode(next);
    setLabs(null);
    setMeds(null);
    setDiagnostics(null);
    setError(null);
  }

  if (!patientId) return <p className="badge err">No patient selected.</p>;
  if (error && !patient && !catalog) return <p className="badge err">{error}</p>;
  if (mode === "timeline" && !patient) return <p>Loading…</p>;

  return (
    <div>
      {patient && (
        <>
          <h1>{patient.canonical_name ?? "Patient"}</h1>
          <p className="muted">
            {patient.phone ?? "no phone"} · login {patient.username ?? "unset"}
            {patient.date_of_birth ? ` · DOB ${patient.date_of_birth}` : ""}
          </p>
        </>
      )}
      <form className="card" onSubmit={(event) => event.preventDefault()}>
        <p className="muted" style={{ marginTop: 0 }}>
          Search this chart using canonical lab, medication, and diagnostic names.
        </p>
        <div className="grid">
          <label>
            Look up
            <select
              value={mode}
              onChange={(event) => onModeChange(event.target.value as Mode)}
              style={{ display: "block", width: "100%", marginTop: 6 }}
            >
              <option value="timeline">Documents in a date range</option>
              <option value="lab">Lab test</option>
              <option value="medication">Medication</option>
              <option value="diagnostic">Diagnostic</option>
            </select>
          </label>
          {mode === "timeline" && (
            <>
              <label>
                From
                <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ display: "block", width: "100%", marginTop: 6 }} />
              </label>
              <label>
                To
                <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ display: "block", width: "100%", marginTop: 6 }} />
              </label>
            </>
          )}
          {mode === "lab" && (
            <label>
              Test
              <select value={test} onChange={(e) => setTest(e.target.value)} required style={{ display: "block", width: "100%", marginTop: 6 }}>
                <option value="">Select a test</option>
                {(catalog?.lab_tests ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                    {item.in_chart ? "" : " (not on this chart yet)"}
                  </option>
                ))}
              </select>
            </label>
          )}
          {mode === "medication" && (
            <label>
              Medication
              <select value={med} onChange={(e) => setMed(e.target.value)} required style={{ display: "block", width: "100%", marginTop: 6 }}>
                <option value="">Select a medication</option>
                {(catalog?.medications ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                    {item.in_chart ? "" : " (not on this chart yet)"}
                  </option>
                ))}
              </select>
            </label>
          )}
          {mode === "diagnostic" && (
            <label>
              Study
              <select value={study} onChange={(e) => setStudy(e.target.value)} required style={{ display: "block", width: "100%", marginTop: 6 }}>
                <option value="">Select a study</option>
                {(catalog?.diagnostics ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                    {item.in_chart ? "" : " (not on this chart yet)"}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {error && <p className="badge err">{error}</p>}
      </form>
      {mode === "timeline" && patient && <ClusteredTimeline patient={patient} />}
      {mode === "lab" && labs && <LabResults name={catalogLabel(catalog?.lab_tests, test)} rows={labs} />}
      {mode === "medication" && meds && <MedResults name={catalogLabel(catalog?.medications, med)} rows={meds} />}
      {mode === "diagnostic" && diagnostics && (
        <DiagnosticResults name={catalogLabel(catalog?.diagnostics, study)} rows={diagnostics} />
      )}
    </div>
  );
}

function catalogLabel(items: { id: string; label: string }[] | undefined, id: string) {
  return items?.find((item) => item.id === id)?.label ?? id;
}

function LabResults({ name, rows }: { name: string; rows: LabQueryRow[] }) {
  if (rows.length === 0) return <p className="muted">No {name} results on this chart.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Test</th>
          <th>Value</th>
          <th>Range</th>
          <th>Document</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.test_date ?? "undated"}</td>
            <td>{row.canonical_name ?? row.raw_name}</td>
            <td>
              {row.value != null ? `${row.value} ${row.unit ?? ""}`.trim() : "—"}
              {row.abnormal_flag ? ` · ${row.abnormal_flag}` : ""}
            </td>
            <td>
              {row.reference_low != null && row.reference_high != null
                ? `${row.reference_low}–${row.reference_high}`
                : "—"}
            </td>
            <td>
              <Link to={`/documents/${row.document_id}`}>{row.filename ?? "Open"}</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MedResults({ name, rows }: { name: string; rows: MedQueryRow[] }) {
  if (rows.length === 0) return <p className="muted">{name} was not prescribed on this chart.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Medication</th>
          <th>Document</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.prescribed_date ?? "undated"}</td>
            <td>{row.line}</td>
            <td>
              <Link to={`/documents/${row.document_id}`}>{row.filename ?? "Open"}</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DiagnosticResults({ name, rows }: { name: string; rows: DiagnosticQueryRow[] }) {
  if (rows.length === 0) return <p className="muted">No {name} reports on this chart.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Study</th>
          <th>Impression</th>
          <th>Document</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.report_date ?? "undated"}</td>
            <td>{row.study ?? name}</td>
            <td>{row.impression ?? "—"}</td>
            <td>
              <Link to={`/documents/${row.document_id}`}>{row.filename ?? "Open"}</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
