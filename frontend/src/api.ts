import { sessionHeaders } from "./session";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  for (const [key, value] of Object.entries(sessionHeaders())) {
    headers.set(key, value);
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      throw new Error(typeof parsed.detail === "string" ? parsed.detail : text);
    } catch (err) {
      if (err instanceof SyntaxError) throw new Error(text || response.statusText);
      throw err;
    }
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function uploadDocument(file: File, targetPatientId?: string) {
  const body = new FormData();
  body.append("file", file);
  if (targetPatientId) body.append("target_patient_id", targetPatientId);
  return api<DocumentSummary & { poll_url: string }>("/documents", { method: "POST", body });
}

export function isInFlight(status: string) {
  return !["PENDING_CONFIRMATION", "COMPLETED", "NEEDS_REVIEW", "FAILED", "CANCELLED"].includes(status);
}

export function confirmDocument(documentId: string) {
  return api<DocumentDetail>(`/documents/${documentId}/confirm`, { method: "POST" });
}

export function discardDocument(documentId: string) {
  return api<{ ok: boolean }>(`/documents/${documentId}/discard`, { method: "POST" });
}

export type DocumentSummary = {
  id: string;
  filename: string;
  document_type: string | null;
  status: string;
  patient_id: string | null;
  patient_name: string | null;
  document_date: string | null;
  needs_review: boolean;
  page_count: number;
  used_ocr: boolean;
  has_native_text: boolean;
  created_at: string | null;
  poll_url?: string;
};

export type DocumentDetail = DocumentSummary & {
  review_reasons: string[];
  processing_log: { stage: string; status: string; message: string; ts: string }[];
  error_message: string | null;
  extracted: unknown;
  pages: { page_number: number; text: string; ocr_used: boolean }[];
  validation_errors: {
    entity_type: string;
    field: string | null;
    code: string;
    message: string;
    severity: string;
  }[];
  link: {
    match_method: string;
    match_reason: string;
    confidence: number;
    needs_review: boolean;
    candidate_patient_ids: string[];
  } | null;
  patient: {
    id: string;
    canonical_name: string | null;
    phone: string | null;
    username: string | null;
    external_patient_id: string | null;
    date_of_birth: string | null;
    needs_review: boolean;
  } | null;
  confirmation?: UploadConfirmation;
};

export type UploadConfirmation = {
  needs_confirmation: true;
  id: string;
  document: DocumentDetail;
  extracted_text: string;
  ocr_error: string | null;
  extracted_patient: {
    name: string | null;
    phone: string | null;
    patient_id: string | null;
    date_of_birth: string | null;
  };
  chart_patient: {
    name: string | null;
    phone: string | null;
    username: string | null;
    patient_id: string | null;
    date_of_birth: string | null;
  };
  warnings: string[];
};

export type PatientSummary = {
  id: string;
  canonical_name: string | null;
  phone: string | null;
  username: string | null;
  external_patient_id: string | null;
  date_of_birth: string | null;
  needs_review: boolean;
  document_count: number;
};

export type TimelineItem = {
  document_id: string;
  filename: string;
  document_type: string | null;
  date: string | null;
  status: string;
  needs_review: boolean;
  summary?: string[];
};

export type TimelineCluster = {
  date: string | null;
  title: string;
  type_label: string;
  description: string;
  document_count: number;
  documents: TimelineItem[];
};

export type PatientDetail = Omit<PatientSummary, "document_count"> & {
  timeline: TimelineItem[];
  clusters: TimelineCluster[];
};

export type CatalogItem = {
  id: string;
  label: string;
  in_chart: boolean;
};

export type ChartCatalog = {
  lab_tests: CatalogItem[];
  medications: CatalogItem[];
  diagnostics: CatalogItem[];
};

export type LabQueryRow = {
  id: string;
  document_id: string;
  filename: string | null;
  test_date: string | null;
  raw_name: string | null;
  canonical_name: string | null;
  value: number | null;
  unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  abnormal_flag: string | null;
};

export type MedQueryRow = {
  id: string;
  document_id: string;
  filename: string | null;
  prescribed_date: string | null;
  canonical_name: string | null;
  raw_name: string | null;
  line: string;
};

export type DiagnosticQueryRow = {
  id: string;
  document_id: string;
  filename: string | null;
  report_date: string | null;
  study: string | null;
  canonical_study: string | null;
  impression: string | null;
};
