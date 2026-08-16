# Engineering decisions - shouldn't be updated by coding tool.

This document records the choices that shape correctness, reliability, cost, and scope for this assignment MVP.

The product problem is: turn messy medical documents into structured, normalized, validated, linked, and queryable data. The domain I am selecting is medical.

There are lot of usecases that can be associated with parsing of medical records. For example
an insurance company can use it to extract data for a patient claims, track patient history
to track genuineness of claim or also someone can keep track of their own medical history
themselves or a doctor - family doctor - can use it to track history of their patients to
give them proper advice. This can be a common patient repository for doctors to gain access to
and check.

How do they gain access to a patients information is also something we can think of because I
don't think the central repository of patients should be exposed to every doctor other than the one that you particularily gave permission to.

The problem other than extracting documents and converting them into structured data what I would like to deal with is this authorization of viewing someone else info itself.

Thus the login would be for health care professional or patient, the patient login would show
them their own details, and an option to genrate a code to share to the doctor - the code would have an expiry of 24 hour from the first time it was generated. Once a new code is generated, the old code would expire. Also there is an option to revoke a token.

The doctor would be able to see history of all the patients which have shared the code with them, this allows the doctor to work on multiple patients in a single day and get back to
them whenever they process the information.

The documents to be processed are limited to prescriptions, laboratory reports, and diagnostic reports.

Also, I would like to have a UX with clustered timelines of the patient, clustering can
be on closeness of the dates, or corelating different documents from different time. But time
based clustering seems fine.

Also each prescription unlike the other documents can have multiple dates, for follow ups
but right not it is okay to not consider that while construction of the timeline - but for
a mature product it would be required.

The notes below are the actual tradeoffs made while building the pipeline, not a retrospective list of unused options.
---

# Decision: Scope of medical document types

## The decision

Support exactly three types: `lab_report`, `prescription`, `diagnostic_report`, plus `unknown` when evidence is weak.

## The alternatives

- Open-ended extraction into a generic key/value bag for any document.
- A larger clinical set (discharge summaries, bills, imaging DICOM, pathology).

## The reasoning

The assignment is about a reliable transformation pipeline, not a complete EHR. Three types are enough to force different schemas, different validation rules, and a shared patient timeline, without pretending one schema fits every medical document.

## What we deliberately cut

Bills, discharge summaries, and “any PDF.” Supporting them would inflate schemas and hide whether the pipeline actually works.

---

# Decision: Overall pipeline architecture

## The decision

An explicit staged pipeline: upload → inspect → local text/OCR → intermediate representation → classify → structured extract → normalize → validate → link → persist → query.

Each stage writes a status onto the document (`TEXT_EXTRACTED`, `OCR_COMPLETED`, `CLASSIFIED`, …) plus a processing log.

## The alternatives

- One function that sends the PDF to a model and stores JSON.
- A job queue / worker architecture (Celery, Redis).

## The reasoning

The engineering value is the pipeline around the model. Stages make failures inspectable (“OCR failed” vs “validation failed”) and let tests target one concern.

Upload returns a document id immediately (`PROCESSING`) and the UI polls `GET /documents/{id}`. The pipeline still runs in-process on a background task after the response is sent. That is not Celery; it is enough so a second upload is not blocked by OCR/LLM.

## What we deliberately cut

A job queue, retries-as-a-platform, and distributed tracing. Re-run is a single `POST /documents/{id}/reprocess`.

---

# Decision: PDF parsing strategy

## The decision

Use PyMuPDF. If a PDF has a usable native text layer (enough characters across pages), extract text and block bounding boxes locally. Only if that layer is missing or too thin do we OCR.

## The alternatives

- Always OCR, even for digital PDFs.
- Always send the PDF bytes to a document-AI / multimodal LLM.

## The reasoning

Native extraction is cheaper, faster, more faithful for born-digital reports, and preserves layout blocks for provenance. OCR introduces recognition error; using it on text PDFs would make the demo worse and hide the inspect step.

## What we deliberately cut

Cloud document-AI parsers. They would collapse the pipeline into a vendor call and make local evaluation harder.

---

# Decision: OCR strategy

## The decision

Local Tesseract via pytesseract, on rasterized pages or uploaded images. Word boxes from `image_to_data` are stored on the intermediate representation. Phone photos are downscaled (longest side 2400px) before OCR so Pillow’s decompression-bomb limit does not block a 90MP camera file, and Tesseract is not asked to ingest tens of millions of pixels.

## The alternatives

- A hosted OCR API.
- EasyOCR / PaddleOCR as the default.

## The reasoning

The assignment asks for a mature local OCR tool. Tesseract is the usual default, has no per-page cost, and keeps scanned PHI (even synthetic) on the machine. EasyOCR would add a large model download for little MVP benefit.

## What we deliberately cut

OCR-as-a-service as the primary extractor, and EasyOCR as the default. Tesseract remains first. The vision model is a **fallback**, not the OCR engine.

---

# Decision: Vision OCR fallback (when Tesseract is not enough)

## The decision

Run local Tesseract first on photos and image-only PDFs. Call a cheap vision model on a downscaled JPEG **only when** all of the following hold:

1. `LLM_MODE` resolves to `gemini` or `openai` (a key is set). This assignment uses **Gemini Flash** (`gemini-flash-latest`) when `GEMINI_API_KEY` is present.
2. The page has **no native PDF text** (we never vision-OCR a text-layer lab PDF).
3. At least one trigger:
   - Tesseract is missing or raised `OCR_FAILED`.
   - The file is a **raster image upload** (jpg/png/webp/tiff): phone photos mix printed letterhead with handwriting; Tesseract can look “successful” on the header and still miss the script.
   - For image-only PDFs: Tesseract text is under 100 characters, **or** at least three words were read and mean confidence is below 0.55.

Vision text replaces the Tesseract page text when the fallback returns anything. If vision is unavailable and Tesseract failed, keep `OCR_FAILED`.

## The alternatives

- EasyOCR as the handwriting engine.
- Vision OCR on every page, including digital PDFs.
- Tesseract only (empty confirm screen on handwritten pads).

## The reasoning

Tesseract is the right default for printed scans and the assignment’s sample PDFs. Handwritten outpatient pads fail that path. EasyOCR is still weak on cursive and heavy to ship. A vision call is justified when Tesseract failed, returned thin/low-confidence text, or the source is a camera image. Printed text-layer PDFs stay local and cheap.

## What we deliberately cut

Always-on multimodal PDF parsing, a second local OCR stack, and specialized handwriting models (TrOCR).

---

# Decision: Gemini Flash as the assignment LLM

## The decision

When `GEMINI_API_KEY` is set, `LLM_MODE=auto` uses **Gemini Flash** (`gemini-flash-latest`) for:

- vision transcription of photos / weak Tesseract pages
- classification (when heuristics are unsure)
- text → structured JSON (labs, prescriptions, diagnostic reports)

OpenAI remains an optional fallback if Gemini is unset. CI stays on the stub extractor.

## The alternatives

- GPT-4o-mini for everything.
- A larger Gemini Pro model.

## The reasoning

This is an assignment, not a clinical product. Flash is cheap enough for photo OCR plus a JSON extract. The pipeline around the model (IR, normalize, validate, link, patient confirm) stays the same.

## What we deliberately cut

Gemini Pro, fine-tuning, and storing the API key in git.

---

# Decision: Intermediate document representation

## The decision

Persist a `DocumentIR`: pages with full text, optional blocks/bboxes, and whether OCR was used. The UI shows this text on the document detail page, before/beside the structured JSON.

## The alternatives

- Pass file bytes straight into the LLM and skip an inspectable IR.
- Store only concatenated plain text.

## The reasoning

Without an IR, you cannot answer “what did we actually extract?” when the model is wrong. Blocks enable later provenance. Truncation for the LLM happens from this IR, not by silently dropping the source.

## What we deliberately cut

A full layout graph or reading-order reconstruction. Page text + blocks is enough to audit the MVP.

---

# Decision: LLM vs deterministic processing

## The decision

Deterministic code owns PDF/OCR, schema checks, date/unit/test-name maps, arithmetic consistency, patient ID matching, and SQL queries.

The LLM is used for classification when heuristics are weak, and for one schema-constrained extraction call per document. A local stub extractor exists for tests and for running sample PDFs without an API key (`LLM_MODE=auto|openai|stub`).

## The alternatives

- LLM for every field, including dates and units.
- No LLM at all (regex-only).

## The reasoning

Regex cannot reliably read messy prescriptions; an LLM cannot be trusted to normalize “g/DL” consistently or to refuse invented reference ranges. Splitting the work keeps cost down (one extract call, not one per field) and keeps correctness testable. The stub is not the product; it is how the pipeline stays demonstrable offline and in CI.

## What we deliberately cut

Embeddings, agents, and multi-step tool-calling loops.

---

# Decision: Structured extraction / schema design

## The decision

Pydantic models per document type, with nulls allowed. Gemini Flash (or OpenAI structured outputs) parse into those models. The model is instructed not to invent fields; absent values stay null and the original span is kept as `source_text`.

## The alternatives

- Free-form JSON and hope the model complies.
- A single mega-schema with optional bags of fields.

## The reasoning

Constrained decoding plus Pydantic is the cheapest way to stop silent schema drift. Separate types keep lab tests from being stuffed into medication rows.

## What we deliberately cut

Per-field extraction calls and “extract everything that might be medical.”

---

# Decision: Normalization strategy

## The decision

After extraction, a deterministic pass maps dates (day-first for numeric dates, matching `12/07/2026` → `2026-07-12`), units (`g/DL` → `g/dL`), lab names (`Haemoglobin` → `hemoglobin`), and a small medication alias list. Raw values are always stored next to canonical ones.

## The alternatives

- Ask the LLM to emit canonical forms directly.
- A large clinical terminology service (LOINC, RxNorm).

## The reasoning

Normalization is a function of known aliases, not medical judgment. Doing it in code makes tests exact and prevents the model from “helpfully” adding units. Day-first parsing is an explicit locale choice for this assignment’s examples and typical Indian lab sheets; US `MM/DD` reports can be wrong — that limitation is accepted and documented.

## What we deliberately cut

LOINC/RxNorm binding. It would look impressive and still be incomplete without a licensing/ops story.

---

# Decision: Validation strategy

## The decision

Deterministic checks only: types, parseable numbers, reference low ≤ high, two values for the same canonical test on one document, internally contradictory flags/frequencies. Failures set `validation_failed` / `needs_review`. We do not apply textbook reference ranges or diagnose.

## The alternatives

- LLM “does this lab look right?”
- Auto-correct the conflicting hemoglobin to the “more likely” value.

## The reasoning

Validation must be explainable in an interview. Invented ranges would be medically unsafe and scientifically fake. Auto-fixing 13.2 vs 8.1 would destroy the point of the inconsistent-document sample.

## What we deliberately cut

Clinical decision support, panic-value alerting, and disease inference from HbA1c.

---

# Decision: Provenance

## The decision

Important fields carry `document_id`, page, `source_text`, optional bbox, and confidence. The canonical JSON shown in the UI includes this object so an evaluator can ask “where did 13.2 come from?”

## The alternatives

- Store only the final number.
- Highlight PDFs with a full overlay viewer.

## The reasoning

Structured data without a trail is not auditable. A PDF overlay would consume UI time without changing the data model.

## What we deliberately cut

Pixel-perfect citation UI. The IR text + provenance JSON is the audit trail.

---

# Decision: Confidence and uncertainty

## The decision

The system distinguishes missing (null), extracted (value + confidence), validation failed, linking ambiguous, and `needs_review`. Low classification confidence also flags review. Nothing is filled in to look complete.

## The alternatives

- A single 0–1 score on the whole document.
- Always emit a “best guess” unit for HbA1c 7.8.

## The reasoning

The HbA1c sample is specifically there to show that a number without a unit stays a number without a unit. Review is a first-class state, not a log line.

## What we deliberately cut

Calibrated probability models. Confidence is heuristic/LLM-reported, not statistically calibrated — that is stated honestly.

---

# Decision: Patient identity resolution

## The decision

Order: exact external patient ID → normalized name + DOB → unique exact normalized name → fuzzy name. Similar names without shared identifiers create a **new** patient flagged `needs_review` and record candidate IDs. We never merge on “P. Nair” ≈ “Priya Nair” alone.

## The alternatives

- Always merge the highest fuzzy score.
- LLM decides whether two patients are the same.

## The reasoning

False merges are worse than duplicate patients in a demo about trust. Deterministic rules can be recited in an interview. Fuzzy matching is a fallback that **escalates**, it does not auto-merge.

## What we deliberately cut

Probabilistic record linkage, household matching, and automatic LLM merge.

---

# Decision: Database choice

## The decision

SQLite via SQLAlchemy, file at `backend/data/app.db`. Tables: patients, documents, document_pages, lab_results, medications, diagnostic_reports, document_links, validation_errors.

## The alternatives

- PostgreSQL from day one.
- Store only JSON blobs.

## The reasoning

SQLite is zero-ops for a local assignment and still gives real SQL over normalized rows (hemoglobin over time). JSON blobs alone would make “queryable” mean “grep the JSON.”

## What we deliberately cut

Postgres, migrations frameworks, and connection pooling. Schema is created on startup.

---

# Decision: Query architecture

## The decision

HTTP query endpoints filter SQL tables (`/query/lab-results?test=hemoglobin`, medications, needs-review). The patient resource returns documents sorted by `document_date`. No LLM-over-PDF search.

## The alternatives

- Natural language to SQL via an LLM.
- Vector search over page text.

## The reasoning

The assignment says NL query is optional and less important than a structured store. SQL answers the listed questions directly and is deterministic in tests.

## What we deliberately cut

Vector databases and NL2SQL. They would not prove the pipeline worked.

---

# Decision: UI scope

## The decision

Four pages: upload, documents, document detail (IR + canonical JSON + validation + provenance + log), patients with a chronological list. A fifth query page hits the SQL endpoints. React + Vite, no component library.

## The alternatives

- A polished clinical chart / timeline visualization.
- Backend-only with curl.

## The reasoning

A thin UI is the fastest way for an evaluator to see messy → structured → queryable. Curl-only would hide the IR vs JSON contrast.

## What we deliberately cut

Auth screens, design systems, print layouts, and a “full medical timeline” product.

---

# Decision: Error handling

## The decision

Stage statuses on the document, including `OCR_FAILED`, `EXTRACTION_FAILED`, `VALIDATION_FAILED`, `LINKING_AMBIGUOUS`, `NEEDS_REVIEW`. The log is an append-only JSON list of `{stage, status, message, ts}`.

## The alternatives

- One `processing_failed` flag.
- Exceptions only in server logs.

## The reasoning

The assignment explicitly forbids hiding failures. An evaluator should see which stage broke on the detail page.

## What we deliberately cut

Dead-letter queues and paging/on-call.

---

# Decision: Reprocessing

## The decision

`POST /documents/{id}/reprocess` re-runs the pipeline from the stored file, replacing derived rows. The document id is stable.

## The alternatives

- Immutable versions of every run.
- Reprocess from IR only (skip OCR).

## The reasoning

Prompt/schema tweaks are expected during evaluation. Full re-run from file is simpler and picks up OCR/parser changes. Version history would be warehouse theater.

## What we deliberately cut

Run history tables and A/B extraction versions.

---

# Decision: Privacy / security

## The decision

Local disk uploads, local SQLite (or a Railway volume at `/data` when hosted), no authentication. README forbids real patient data. API keys live in `.env` or host secrets, never in git. CORS allows local Vite/dev and `*` only in the container demo.

## The alternatives

- JWT auth and user accounts.
- Encrypt-at-rest and audit logs.

## The reasoning

This is a local assignment, not a covered entity’s production system. Auth would consume the time that should go to validation and linking. Using real PHI would be the actual privacy failure.

## What we deliberately cut

SSO, HIPAA program claims, and deployment hardening. Do not put real records in this repo.

---

# Decision: Testing strategy

## The decision

Tests target decisions: native vs image-only PDF inspection, date/unit/name maps, lab inconsistency, prescription missing name, exact ID linking, ambiguous P. Nair vs Priya Nair, and a stub-LLM end-to-end process. No live OpenAI in CI.

## The alternatives

- Snapshot the full UI.
- 100% line coverage.

## The reasoning

Coverage of failure modes is what an evaluator can read in ten minutes. UI snapshots would flake; hitting OpenAI would make CI need a key and money.

## What we deliberately cut

Browser E2E and load tests.

---

# Decision: Deliberately excluded functionality

## The decision

No Kubernetes, microservices, vector DB, knowledge graph, diagnosis, treatment advice, production auth, cloud OCR/Document AI, RxNorm/LOINC, or a consumer medical app.

## The alternatives

Each of those is a reasonable production conversation and the wrong scoring function for a short assignment.

## The reasoning

Every extra subsystem would dilute evidence that messy documents become queryable rows. The cut list is the product: a pipeline you can clone, run, break with sample 06 and 08, and explain from this file.

## What we deliberately cut

Listed above; that is the point of this decision.

---

# Decision: Single-process demo hosting

## The decision

Serve the Vite production build from FastAPI on one port. Ship one Docker image (Python + Tesseract + static UI) and deploy that to Railway if a public URL is required. SQLite and uploads live on a volume at `/data`.

## The alternatives

- Two services (Vercel UI + Render API).
- Kubernetes / managed Postgres.
- No public URL (clone-and-run only).

## The reasoning

One container keeps CORS simple (same origin), includes OCR, and avoids turning the assignment into platform engineering. Railway is a volume + env-var host, not a production architecture.

## What we deliberately cut

Auth, custom domains, autoscaling, and Postgres. The hosted app is still a demo: do not upload real records.

---

# Decision: Refuse filing a document on the wrong patient

## The decision

Access control only answers “may this clinician see Aarav’s chart?” Filing still requires identity confirmation against the **selected** chart. New uploads (patient or clinician) show extracted text and warnings, then attach only after confirm. The hard check below still applies to **reprocess**:

1. If the document has a patient ID **and** the chart has one, the IDs must match (case-insensitive). A strong name conflict still fails even when IDs match.
2. If the document has **no** patient ID, a fuzzy name match is required (`rapidfuzz` `token_sort_ratio`; a weaker overall score can pass if last names agree). Thresholds match linking: strong ≥ 92, weak ≥ 70 with last-name ≥ 80. Priya Nair cannot be filed on Aarav Sharma.
3. If the document has neither ID nor a usable name, filing is refused. Missing identity is not treated as a match.
4. Date-of-birth conflicts fail when both sides have a DOB.

We do **not** make patient ID mandatory on PDFs. `07_lab_priya.pdf` (and many real labs) only print a name. Fuzzy name is the no-ID path; that lab is valid on Priya’s chart, not Aarav’s.

### Cleanup on a failed **new** upload

A failed pipeline after the file is stored **deletes** the partial state. Cancel on the confirmation screen does the same:

- the stored PDF on disk
- the `documents` row and cascaded children (pages, labs, meds, report, links, validation errors)
- a `patients` row created only by that upload (zero remaining documents), so a rejected Priya lab does not leave an empty Priya patient

The document is processed **unattached**, then parked as `PENDING_CONFIRMATION` on the selected chart until confirm or cancel. We do not auto-file a mismatched Priya lab onto Aarav’s timeline.

### Reprocess

Reprocess of an existing document must **not** delete it. If identity no longer matches the owner, restore the previous `patient_id` and return 409.

## The alternatives

- Trust the clinician’s selected patient with no document check.
- Leave failed uploads as `NEEDS_REVIEW` orphans on the wrong timeline.
- Require a patient ID on every document (would reject real name-only labs).
- Auto-move a mismatched file onto the extracted patient (surprising; the clinician picked a chart on purpose).

## The reasoning

The first version of this check returned “compatible” when extraction found no name **and** no ID. That is how a Priya lab could still land on Aarav: the sample has no `PAT-…` id, a missed name extract was treated as “nothing to contradict,” and the file was assigned to the selected chart. Fuzzy name matching is the fallback when labs omit MRN/patient ID. Confirmation plus warnings keeps the user in the loop; deleting a cancelled or failed upload keeps the database honest.

## What we deliberately cut

A full MPI, auto-moving the file onto the extracted patient, and requiring IDs on every sample PDF. Name-only labs remain valid **for the matching patient**.

---

# Decision: Create a patient account on first unknown login

## The decision

`POST /auth/patient` looks up the entered **username** (`username`, then legacy `external_patient_id`, then internal UUID). If none exists, it creates a patient with that username and stores a hash of the submitted password. Name and phone on that request are stored as identity when present. Later logins for that username must match the stored password.

Patients created by document linking have no password hash; they still accept `DEMO_PATIENT_PASSWORD` (`demo`). The same rule applies to clinicians: unknown IDs create an account; `DOC-1001` stays on `demo` until it has a stored password.

## The alternatives

- Reject unknown IDs (patients can only exist after a PDF is uploaded).
- Keep one shared password for every patient forever.
- Full signup with email verification.

## The reasoning

A patient should be able to open an empty chart and then upload or share, without waiting for a document to invent their ID. Storing a per-account hash means a newly created `PAT-3001` is not unlocked by the global demo password. Document-created sample patients stay demo-friendly.

## What we deliberately cut

Email, password reset, and real identity proofing. This is still a demo gate, not hospital IAM.

---

# Decision: Uploads confirm extracted text before filing

## The decision

When a **patient or clinician** uploads a document, the pipeline runs first, then the UI shows a confirmation step:

1. Always show the extracted text (OCR or native).
2. Compare extracted **name and phone** (and DOB if present) to the selected chart. Hospital MRN/`patient_id` is shown as metadata only.
3. Warn if a name or phone could not be extracted, or if they differ from the chart (including an empty chart that has only a username).
4. Attach to that chart **only after** confirm. Cancel deletes the pending file and does not leave it on the timeline.
5. Confirm **fills empty chart name/phone/DOB/hospital ID** from the document and files the document as `COMPLETED` unless real validation errors remain. Identity warnings are not kept as `needs_review`.

A clinician asserting “file this on the patient I selected” can override missing or inexact extraction the same way a patient can.

Pending documents use status `PENDING_CONFIRMATION` and are omitted from timelines, lists, and queries until confirmed.

## The alternatives

- Auto-file on the selected patient with no review (wrong-chart risk; empty-chart 409).
- Hard 409 for clinicians only (blocks a real prescription when extraction misses the name).
- Auto-move the file onto a newly extracted patient identity.

## The reasoning

Login-created patients often have a username and no name. Real prescriptions print a hospital name/MRN the extractor may miss. Showing the text lets the uploader verify the file before it becomes part of the history. Confirming means “this belongs on this chart,” so extracted name and phone are copied onto empty identity fields instead of leaving a permanent review flag.

## What we deliberately cut

A full document viewer and field-by-field correction. Confirm or discard; do not edit extraction in this MVP.

---

# Decision: Patients are identified by name and phone

## The decision

A person on a chart is **name + phone**. Username is only a login handle. Hospital MRN / `PAT-…` / document `patient_id` is metadata stored when extracted, not the identity key.

- Login looks up `username` (with a fallback to old `external_patient_id` so sample charts still open).
- Document linking prefers name+phone, then phone, then name+DOB. It does not merge two people because they share a hospital ID.
- Confirmation warnings compare name and phone, not hospital ID.
- Share access still uses username + code so a clinician can find the account.

## The alternatives

- Treat hospital MRN / `PAT-1001` as the person (breaks when the same human has different IDs, or when a login ID is not printed on the PDF).
- Identify only by name (too many collisions).
- Require phone on every PDF (many labs omit it).

## The reasoning

People do not walk around as `PAT-1001`. Login needs a handle; clinical identity needs name and a phone number. Documents that omit phone still confirm onto the selected chart and can fill the phone later.

## What we deliberately cut

OTP verification of the phone, Aadhaar, and a full master patient index.

---

# Decision: Upload returns an id; the UI polls

## The decision

`POST /documents` stores the file, assigns it to the selected chart, sets status `PROCESSING`, and returns `{ id, poll_url, ... }` before OCR/LLM run. A FastAPI background task runs the existing pipeline, then parks the file as `PENDING_CONFIRMATION`.

The documents list includes processing and unconfirmed files. Timeline and queries still omit them until confirm. The UI polls every 2 seconds while status is in-flight and stays usable for more uploads.

## The alternatives

- Keep the HTTP request open until extraction finishes (blocks the page and a second upload).
- Celery/Redis workers (too much ops for this MVP).

## The reasoning

Gemini/OCR can take tens of seconds. The user should queue the next file instead of watching a disabled button. Polling one document resource is enough; we did not add websockets.

## What we deliberately cut

A durable job queue, progress percentages, and cancelling an in-flight model call mid-token.

---

# Decision: Chart-scoped search on the timeline

## The decision

Structured search lives on the **patient timeline page**, for both patient and clinician. There is no separate Query UI.

The user picks a lookup type and a **canonical name** from a maintained catalog (lab tests, medications, diagnostic studies), or a date range. Results are typed:

- date range → clustered timeline
- lab → value, unit, range, document link
- medication → dose line and document link
- diagnostic → study, impression, document link

`GET /patients/{id}/catalog` unions the alias lists with names already on that chart. Global `/query/*` SQL endpoints remain for assignment proof; they are not the product UI.

## The alternatives

- One JSON query page for clinicians.
- Natural language to SQL.

## The reasoning

A family doctor and a patient ask “was amoxicillin given?” and “what is hemoglobin?” on **this chart**. Canonical pickers avoid spelling drift (`Hb` vs hemoglobin). JSON dumps do not prove the pipeline is usable.

## What we deliberately cut

NL2SQL, vector search, and cross-patient worklists on this screen.


