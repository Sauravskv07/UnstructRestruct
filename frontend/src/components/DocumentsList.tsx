import { Link } from "react-router-dom";
import { DocumentSummary, isInFlight } from "../api";

export default function DocumentsList({ rows }: { rows: DocumentSummary[] }) {
  if (rows.length === 0) {
    return <p className="muted">No documents yet.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Filename</th>
          <th>Type</th>
          <th>Patient</th>
          <th>Date</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>
              <Link to={`/documents/${row.id}`}>{row.filename}</Link>
            </td>
            <td>{row.document_type ?? "—"}</td>
            <td>{row.patient_name ?? "—"}</td>
            <td>{row.document_date ?? "—"}</td>
            <td>
              <span
                className={`badge ${
                  row.status === "FAILED"
                    ? "err"
                    : row.status === "PENDING_CONFIRMATION" || row.needs_review
                      ? "warn"
                      : ""
                }`}
              >
                {isInFlight(row.status) ? "processing" : row.status.replace(/_/g, " ").toLowerCase()}
              </span>
              {row.status === "PENDING_CONFIRMATION" && (
                <>
                  {" "}
                  <Link to={`/documents/${row.id}`}>Confirm</Link>
                </>
              )}
              {row.used_ocr ? " OCR" : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
