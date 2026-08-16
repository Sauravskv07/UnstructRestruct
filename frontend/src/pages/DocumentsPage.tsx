import { useEffect, useState } from "react";
import { api, DocumentSummary, isInFlight } from "../api";
import DocumentsList from "../components/DocumentsList";

export default function DocumentsPage() {
  const [rows, setRows] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    return api<DocumentSummary[]>("/documents")
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!rows.some((row) => isInFlight(row.status))) return undefined;
    const timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [rows]);

  return (
    <div>
      <h1>Documents</h1>
      {error && <p className="badge err">{error}</p>}
      <DocumentsList rows={rows} />
    </div>
  );
}
