import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  CatalogItem,
  DiagnosticQueryRow,
  LabQueryRow,
  MedQueryRow,
  PatientDetail,
} from "../api";
import ClusteredTimeline from "../components/ClusteredTimeline";
import { loadSession } from "../session";

type Mode = "timeline" | "lab" | "medication" | "diagnostic";

const KIND: Record<Exclude<Mode, "timeline">, string> = {
  lab: "lab_test",
  medication: "medication",
  diagnostic: "diagnostic",
};

export default function TimelinePage() {
  const { id } = useParams();
  const session = loadSession();
  const patientId = id ?? (session?.role === "patient" ? session.patientId : undefined);
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("timeline");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [test, setTest] = useState<CatalogItem | null>(null);
  const [med, setMed] = useState<CatalogItem | null>(null);
  const [study, setStudy] = useState<CatalogItem | null>(null);
  const [labs, setLabs] = useState<LabQueryRow[] | null>(null);
  const [meds, setMeds] = useState<MedQueryRow[] | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticQueryRow[] | null>(null);

  useEffect(() => {
    if (!patientId) {
      setError("No patient selected.");
      return;
    }
    if (mode !== "timeline") return;
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
    const params = new URLSearchParams({ test: test.id });
    api<LabQueryRow[]>(`/patients/${patientId}/lab-results?${params}`)
      .then(setLabs)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, test]);

  useEffect(() => {
    if (!patientId || mode !== "medication" || !med) {
      if (mode !== "medication") setMeds(null);
      return;
    }
    const params = new URLSearchParams({ name: med.id });
    api<MedQueryRow[]>(`/patients/${patientId}/medications?${params}`)
      .then(setMeds)
      .catch((err: Error) => setError(err.message));
  }, [patientId, mode, med]);

  useEffect(() => {
    if (!patientId || mode !== "diagnostic" || !study) {
      if (mode !== "diagnostic") setDiagnostics(null);
      return;
    }
    const params = new URLSearchParams({ study: study.id });
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
  if (error && !patient && mode === "timeline") return <p className="badge err">{error}</p>;
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
          Type a lab, medication, or study name. Matches come from every document in the system, then this chart is filtered.
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
          {mode !== "timeline" && (
            <NameSearch
              patientId={patientId}
              kind={KIND[mode]}
              label={mode === "lab" ? "Test" : mode === "medication" ? "Medication" : "Study"}
              selected={mode === "lab" ? test : mode === "medication" ? med : study}
              onSelect={mode === "lab" ? setTest : mode === "medication" ? setMed : setStudy}
            />
          )}
        </div>
        {error && <p className="badge err">{error}</p>}
      </form>
      {mode === "timeline" && patient && <ClusteredTimeline patient={patient} />}
      {mode === "lab" && labs && <LabResults name={test?.label ?? test?.id ?? ""} rows={labs} />}
      {mode === "medication" && meds && <MedResults name={med?.label ?? med?.id ?? ""} rows={meds} />}
      {mode === "diagnostic" && diagnostics && (
        <DiagnosticResults name={study?.label ?? study?.id ?? ""} rows={diagnostics} />
      )}
    </div>
  );
}

function NameSearch({
  patientId,
  kind,
  label,
  selected,
  onSelect,
}: {
  patientId: string;
  kind: string;
  label: string;
  selected: CatalogItem | null;
  onSelect: (item: CatalogItem | null) => void;
}) {
  const [text, setText] = useState(selected?.label ?? "");
  const [hits, setHits] = useState<CatalogItem[]>([]);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLLabelElement>(null);

  useEffect(() => {
    setText(selected?.label ?? "");
  }, [kind, selected?.id, selected?.label]);

  useEffect(() => {
    const q = text.trim();
    if (selected && q === selected.label) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      const params = new URLSearchParams({ kind, q });
      api<CatalogItem[]>(`/patients/${patientId}/catalog?${params}`)
        .then((rows) => {
          setHits(rows);
          setOpen(true);
        })
        .catch(() => setHits([]));
    }, 180);
    return () => window.clearTimeout(handle);
  }, [kind, patientId, text, selected]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function choose(item: CatalogItem) {
    onSelect(item);
    setText(item.label);
    setOpen(false);
  }

  return (
    <label ref={box} className="suggest">
      {label}
      <input
        value={text}
        placeholder="Start typing a name"
        autoComplete="off"
        onChange={(event) => {
          setText(event.target.value);
          onSelect(null);
        }}
        onFocus={() => hits.length && setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && hits[0]) {
            event.preventDefault();
            choose(hits[0]);
          }
        }}
        style={{ display: "block", width: "100%", marginTop: 6 }}
      />
      {open && hits.length > 0 && (
        <ul className="suggest-list">
          {hits.map((item) => (
            <li key={item.id}>
              <button type="button" className="suggest-item" onClick={() => choose(item)}>
                <span>{item.label}</span>
                <span className="muted">{item.in_chart ? "on this chart" : "seen in other records"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
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
