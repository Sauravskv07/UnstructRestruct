import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, confirmDocument, discardDocument, DocumentDetail, isInFlight } from "../api";
import { loadSession } from "../session";

export default function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const session = loadSession();

  useEffect(() => {
    if (!id || id === "undefined") {
      setError("Document not found. Go back to Upload and confirm the file instead of refreshing this page.");
      return;
    }
    let cancelled = false;
    let timer: number | undefined;
    function load() {
      api<DocumentDetail>(`/documents/${id}`)
        .then((result) => {
          if (cancelled) return;
          setDoc(result);
          if (!isInFlight(result.status) && timer) window.clearInterval(timer);
        })
        .catch((err: Error) => {
          if (!cancelled) setError(err.message);
        });
    }
    load();
    timer = window.setInterval(load, 2000);
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [id]);

  async function onConfirm() {
    if (!doc) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await confirmDocument(doc.id);
      setDoc(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not confirm");
    } finally {
      setBusy(false);
    }
  }

  async function onDiscard() {
    if (!doc) return;
    setBusy(true);
    setError(null);
    try {
      await discardDocument(doc.id);
      navigate("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not discard");
    } finally {
      setBusy(false);
    }
  }

  if (error && !doc) return <p className="badge err">{error}</p>;
  if (!doc) return <p>Loading…</p>;

  const pending = doc.status === "PENDING_CONFIRMATION";
  const processing = isInFlight(doc.status);
  const confirmation = doc.confirmation;
  const canAccept = pending || (doc.needs_review && !processing);

  return (
    <div>
      <h1>{doc.filename}</h1>
      <p className="muted">
        {doc.document_type} · {doc.status} · {doc.used_ocr ? "OCR" : "native text"} · {doc.page_count} page(s)
      </p>
      {processing && <p className="badge">Processing this file. You can upload others in the meantime.</p>}
      {doc.status === "FAILED" && doc.error_message && <p className="badge err">{doc.error_message}</p>}
      {canAccept && (
        <div className="card">
          <strong>{pending ? "Confirm this document" : "Accept extracted details"}</strong>
          <p className="muted">
            {pending
              ? "Review the extracted text below. Attach it only after you confirm."
              : "Confirmation copies name and phone onto the chart and removes identity warnings. Validation errors stay if they are real data problems."}
          </p>
          {confirmation && (
            <>
              <p>
                <strong>Extracted identity:</strong> {confirmation.extracted_patient.name ?? "no name"}
                {confirmation.extracted_patient.phone ? ` · ${confirmation.extracted_patient.phone}` : " · no phone"}
              </p>
              {confirmation.warnings.map((warning) => (
                <p key={warning} className="badge warn">
                  {warning}
                </p>
              ))}
            </>
          )}
          {session?.role !== "patient" && session?.role !== "clinician" && (
            <p className="badge warn">Sign in to confirm or discard this upload.</p>
          )}
          <div className="confirm-actions">
            <button type="button" onClick={onConfirm} disabled={busy || !session}>
              {busy
                ? "Saving…"
                : pending
                  ? session?.role === "clinician"
                    ? "Yes, attach to this patient"
                    : "Yes, attach to my record"
                  : "Use extracted details"}
            </button>
            {pending && (
              <button type="button" className="secondary" onClick={onDiscard} disabled={busy || !session}>
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
      {error && doc && <p className="badge err">{error}</p>}
      {doc.patient && (
        <p>
          Patient: <Link to={`/patients/${doc.patient.id}`}>{doc.patient.canonical_name ?? "unnamed"}</Link>
          {doc.patient.phone ? ` · ${doc.patient.phone}` : ""}
          {doc.patient.username ? ` · login ${doc.patient.username}` : ""}
        </p>
      )}
      {doc.needs_review && (
        <div className="card">
          <strong>Needs review</strong>
          <ul>
            {doc.review_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="grid">
        <div className="card">
          <h2>Processing log</h2>
          <ul>
            {doc.processing_log.map((entry) => (
              <li key={entry.ts + entry.status}>
                {entry.status}
                {entry.message ? ` — ${entry.message}` : ""}
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2>Linking</h2>
          {doc.link ? (
            <p>
              {doc.link.match_method}: {doc.link.match_reason} (confidence {doc.link.confidence})
            </p>
          ) : (
            <p>No link record.</p>
          )}
        </div>
      </div>
      <div className="card">
        <h2>Validation</h2>
        {doc.validation_errors.length === 0 ? (
          <p>No validation issues.</p>
        ) : (
          <ul>
            {doc.validation_errors.map((issue) => (
              <li key={issue.code + issue.message}>
                <span className={`badge ${issue.severity === "error" ? "err" : "warn"}`}>{issue.code}</span>{" "}
                {issue.message}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="card">
        <h2>Canonical structured data</h2>
        <pre>{JSON.stringify(doc.extracted, null, 2)}</pre>
      </div>
      <div className="card">
        <h2>Extracted text (pre-LLM)</h2>
        {doc.pages.map((page) => (
          <div key={page.page_number}>
            <h3>
              Page {page.page_number}
              {page.ocr_used ? " (OCR)" : ""}
            </h3>
            <pre>{page.text || "(empty)"}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
