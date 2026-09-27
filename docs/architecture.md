# JobEligAI Architecture

## 1. Project overview

JobEligAI is a college micro-project for explaining whether a candidate appears to meet the eligibility requirements in a public-sector recruitment notification.

The system accepts a recruitment notification PDF, extracts its text, converts the eligibility rules into validated structured data, compares those rules with a candidate profile, and presents a criterion-level result:

- `ELIGIBLE`
- `NOT_ELIGIBLE`
- `NEEDS_VERIFICATION`

JobEligAI is an assistance and explainability tool, not an official recruitment decision-maker. The original notification remains the authoritative source.

The design uses a two-stage AI pipeline:

1. Gemini PDF document processing extracts page-aware text or Markdown from the PDF.
2. Google Gemini interprets the extracted text and produces factual summaries and structured eligibility data.

Python remains responsible for deterministic checks such as age, marks, CGPA, and experience. AI output is validated before it is stored or used by the frontend.

Candidate matching, criterion-level results, and final eligibility decisions are
implemented in Phase 6, not in the Phase 5 extraction pipeline.

Phase 6 adds owner-scoped matching endpoints. FastAPI loads the authenticated
candidate profile and latest validated extraction, evaluates objective criteria in
Python, sends only remaining textual criteria to Gemini, validates the structured
semantic response, persists criterion rows, and conservatively reconciles the
overall result. A deterministic failure cannot be overridden by Gemini.

## 2. Technology stack

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React.js | Forms, upload flow, authentication session, API calls, result and history views |
| Backend | Python FastAPI | REST API, authorization, orchestration, validation, deterministic checks, and AI integration |
| Database | Supabase PostgreSQL | Candidate profiles, notifications, extracted criteria, results, and audit data |
| File storage | Supabase Storage | Private storage for uploaded recruitment PDFs |
| Authentication | Supabase Auth | Email/password authentication and JWT sessions |
| OCR | Gemini PDF document processing API | PDF-to-text/Markdown extraction while preserving page boundaries |
| LLM | Google Gemini API | Recruitment summarization and eligibility extraction in Phase 5; matching and explanations are later-phase work |
| Validation | Pydantic | Validation of request data and AI-generated JSON |

The project intentionally avoids microservices, Kubernetes, Celery, Redis, custom model training, and other infrastructure that is not needed for a college-scale application.

## 3. System architecture

The browser communicates with FastAPI for application data and processing. All privileged Supabase access and all Gemini/Gemini calls remain server-side.

```text
React frontend
    |
    | HTTPS REST requests with Supabase access token
    v
FastAPI backend
    |              \
    |               \-- Gemini PDF document processing API
    |
    +-- Supabase Auth verification
    +-- Supabase PostgreSQL
    +-- Supabase Storage
    \-- Google Gemini API
```

The backend is the orchestration boundary. It validates the authenticated user, accepts and validates files, stores the source document, invokes OCR, validates Gemini responses, performs deterministic checks, reconciles the final result, and returns a stable JSON contract to React.

## 4. Complete data flow

1. A user registers or signs in through Supabase Auth from the React application.
2. React receives a Supabase JWT and attaches it to FastAPI requests.
3. The user uploads a recruitment PDF through React.
4. FastAPI verifies the JWT, validates the file type and size, creates a notification record, and uploads the PDF to a private Supabase Storage bucket.
5. FastAPI sends the stored PDF to Gemini PDF document processing.
6. Gemini returns page-aware text or Markdown. FastAPI stores the OCR output and page count.
7. FastAPI sends the OCR text to Gemini for a factual summary and structured eligibility extraction.
8. FastAPI validates both Gemini outputs with Pydantic and stores the extraction and summary.
10. The user completes or updates one active candidate profile.
11. Candidate matching and final eligibility checking are reserved for Phase 6.
12. FastAPI loads the user-owned notification, extracted criteria, and candidate profile.
13. Python runs deterministic checks for numeric and boolean criteria.
14. FastAPI sends the criteria, candidate profile, and deterministic results to Gemini for semantic matching and explanations.
15. FastAPI validates Gemini's matching response and reconciles numeric criteria using Python's results as the authoritative result.
16. FastAPI computes the overall status. Missing or ambiguous information produces `NEEDS_VERIFICATION`, never an assumed pass.
17. FastAPI stores the overall result and individual criterion results.
18. React renders the overall status, criterion cards, explanations, missing information, warnings, and source/page references.
19. The same stored result is available in the user's history.

## 5. Frontend responsibilities

React is responsible for:

- Registration, login, logout, and maintaining the Supabase Auth session.
- Attaching the current JWT to FastAPI requests.
- Uploading recruitment PDFs through the backend.
- Showing upload validation and processing states.
- Rendering the candidate profile form and client-side usability validation.
- Calling notification, profile, and eligibility endpoints.
- Rendering notification summaries and extracted criteria.
- Rendering criterion-level eligibility results and source references.
- Showing `ELIGIBLE`, `NOT_ELIGIBLE`, and `NEEDS_VERIFICATION` states clearly.
- Displaying API errors without inventing fallback results.
- Showing a history of the user's prior checks.

React must not:

- Call Gemini or Gemini directly.
- Use the Supabase service-role key.
- Read or write application tables directly.
- Treat an absent field as a passing value.
- Reimplement final eligibility business rules independently of FastAPI.

## 6. FastAPI responsibilities

FastAPI is responsible for:

- Verifying Supabase JWTs and identifying the current user.
- Enforcing ownership checks on every user-owned resource.
- Validating PDF type, size, and upload metadata.
- Uploading and retrieving files through Supabase Storage.
- Creating and updating notification records.
- Calling Gemini PDF document processing and storing page-aware OCR output.
- Calling Gemini for recruitment summarization and eligibility extraction in Phase 5.
- Validating all AI responses with Pydantic models.
- Normalizing and validating candidate profile data.
- Running deterministic numeric checks.
- Candidate matching, deterministic candidate checks, final status, and criterion-level results are later-phase responsibilities.
- Returning consistent JSON responses and explicit error responses.
- Logging failures without exposing secrets or sensitive credentials.

The backend should keep provider-specific code in service modules so API routes remain focused on HTTP concerns and orchestration.

## 7. Supabase responsibilities

Supabase provides:

- Email/password authentication through Supabase Auth.
- PostgreSQL persistence for profiles, notifications, criteria, results, and criterion details.
- A private Storage bucket for recruitment PDFs.
- Row-level security as a defense-in-depth measure for tables accessed through Supabase.

FastAPI uses the server-side service-role credential only in backend configuration. The service-role credential bypasses RLS and must never be sent to the browser. Backend queries must still include the authenticated user's ownership condition because application-level authorization remains required.

The frontend may use the public Supabase configuration for Auth session operations only. It should not use the public client for application data access in this architecture.

## 8. Gemini PDF document processing pipeline

Gemini PDF document processing is the document extraction stage and is not responsible for deciding eligibility.

The pipeline is:

1. FastAPI validates and stores the original PDF.
2. FastAPI sends the PDF to Gemini PDF document processing using a server-side API key.
3. Gemini returns extracted text or Markdown organized by page.
4. FastAPI preserves page boundaries and page numbers in the stored OCR text.
5. FastAPI records OCR status, page count, and provider errors.
6. The page-aware OCR text becomes the input to Gemini.

Preserving page boundaries is important because explanations should reference the original notification, for example `Page 2, Section 3`. OCR failure must produce an explicit processing failure state and a retryable API error rather than an empty successful extraction.

## 9. Gemini pipeline

Gemini is used in separate, constrained calls rather than one free-form eligibility decision.

### Eligibility extraction

Input: page-aware OCR text.

Output: validated structured criteria, including as applicable:

- Job title, organization, posts, and vacancies.
- Accepted degrees and branches.
- Minimum percentage and/or CGPA.
- Age limits and relaxation rules.
- Category, nationality, experience, and certification requirements.
- Other requirements, exceptions, uncertainty markers, and source references.

### Notification summarization

Input: page-aware OCR text.

Output: a concise validated summary containing important dates, posts, vacancies, application information, and notable requirements.

### Semantic matching

Input:

- Extracted eligibility JSON.
- Candidate profile JSON.
- Python deterministic-check results.

Output: validated criterion-level statuses, candidate and required values, explanations, missing information, warnings, and source references.

Gemini may interpret qualification equivalence, branch wording, certifications, and ambiguous natural-language requirements. It must not silently turn missing information into a pass. Gemini responses are treated as proposals that are validated and reconciled by FastAPI.

## 10. Candidate profile flow

1. React loads the current user's profile, if one exists.
2. The user submits identity, education, category, experience, certification, and other relevant fields to FastAPI.
3. FastAPI validates the request using a Pydantic schema.
4. FastAPI upserts one active profile for the authenticated user.
5. FastAPI returns the normalized profile.
6. During a check, FastAPI reads the profile server-side and sends only the necessary fields to Gemini.

The profile should support nullable fields because not every candidate can provide every value. A missing field is represented explicitly and can cause `NEEDS_VERIFICATION` when the corresponding notification criterion requires it.

Typical fields include:

- Full name.
- Date of birth.
- Category.
- Degree and branch.
- Percentage and/or CGPA.
- Graduation year.
- Experience in years.
- Certifications.
- Nationality.
- Additional structured information where needed.

## 11. Eligibility matching flow

For a requested notification and the authenticated user's profile, FastAPI:

1. Confirms that the notification belongs to the user.
2. Loads the latest validated eligibility extraction.
3. Loads the user's candidate profile.
4. Runs deterministic checks.
5. Sends criteria, profile data, and deterministic results to Gemini for semantic matching.
6. Validates the matching response with Pydantic.
7. Replaces or rejects conflicting numeric results using the deterministic result.
8. Marks criteria with missing or ambiguous inputs as `NEEDS_VERIFICATION`.
9. Derives the overall status from all criterion results.
10. Stores the overall result and one row per criterion.

The overall result should be conservative:

- Any failed required criterion produces `NOT_ELIGIBLE`.
- No failed criterion but at least one required unknown or ambiguous criterion produces `NEEDS_VERIFICATION`.
- `ELIGIBLE` is used only when all required criteria are satisfactorily established.

An explanation should identify the requirement, the candidate value, the comparison or interpretation, and the source page/section when available.

## 12. Deterministic validation flow

Python performs checks where the input and requirement have a clean numeric or boolean shape.

Examples:

- Calculate age from date of birth and the notification's applicable reference date.
- Compare age with minimum and maximum limits.
- Compare percentage with a minimum percentage.
- Compare CGPA with a minimum CGPA.
- Compare experience years with a minimum or maximum.
- Compare graduation year with a stated year range.

Each deterministic check should return a structured outcome containing:

- Criterion name.
- Status: pass, fail, or needs verification.
- Candidate value.
- Required value.
- Explanation.
- Whether the check was performed deterministically.

Missing values, malformed values, unclear dates, and unsupported numeric formats must produce `NEEDS_VERIFICATION`. Python's deterministic result is authoritative for that criterion when the comparison is valid, even if Gemini suggests a different numeric conclusion.

Semantic checks such as degree equivalence, related branches, and interpretation of free-text exceptions remain in Gemini, subject to Pydantic validation and conservative reconciliation.

## 13. Main database entities

The exact schema will be defined in a later implementation task. The primary entities are:

### Candidate profile

One active profile per user for the initial micro-project. It stores education, demographic eligibility fields, experience, certifications, and other candidate information.

### Job notification

Represents an uploaded recruitment PDF. It stores the owner, title, private Storage path, file metadata, processing status, OCR text, page count, summary, and processing errors.

### Extracted eligibility

Represents a versioned, validated eligibility extraction for a notification. The raw structured JSON is the source of truth; commonly queried fields may also be stored in flattened columns.

### Eligibility result

Represents one check of one notification against one candidate profile. It stores the overall status, missing information, warnings, final explanation, raw matching output, owner, and timestamps.

### Criterion result

Represents one criterion in an eligibility result. It stores the criterion name, status, candidate value, required value, explanation, source reference, checking method, and display order.

All entities containing user-owned data must be protected by ownership checks and appropriate database policies.

## 14. Main REST API groups

The endpoint names are illustrative and will be finalized with the implementation schemas.

### Health and session

- `GET /health`
- `GET /me`

### Job notifications

- `POST /jobs` - upload a recruitment PDF and create a notification.
- `GET /jobs` - list the current user's notifications.
- `GET /jobs/{job_id}` - retrieve notification status and metadata.
- `POST /jobs/{job_id}/process` - run or retry OCR and structured extraction.
- `GET /jobs/{job_id}/summary` - retrieve the validated summary.
- `GET /jobs/{job_id}/criteria` - retrieve extracted eligibility criteria.

### Candidate profiles

- `GET /candidates/profile`
- `PUT /candidates/profile`

### Eligibility

- `POST /jobs/{job_id}/check-eligibility`
- `GET /eligibility/{result_id}`
- `GET /eligibility/history`

All application endpoints except health should require a valid Supabase JWT. Every resource lookup must verify that the current user owns or is authorized to access the resource.

## 15. Security boundaries

### Browser boundary

- React may hold the public Supabase Auth configuration and the user's short-lived/session JWT.
- React must never hold `SUPABASE_SECRET_KEY`, `Gemini_API_KEY`, or `GEMINI_API_KEY`.
- React must never call provider APIs directly.
- Uploaded files should be sent to FastAPI over HTTPS.

### FastAPI boundary

- Secrets are loaded from backend environment variables.
- Authorization is checked on every protected request.
- File type and size are validated before storage or OCR.
- User IDs are taken from the verified token, not trusted from request bodies.
- Database and Storage access is scoped to the authenticated user.
- Provider errors are translated into safe, useful API errors without leaking keys or internal traces.
- Logs must not contain API keys, JWTs, or unnecessary personal data.

### Supabase boundary

- The Storage bucket containing recruitment PDFs is private.
- Service-role access is server-side only.
- RLS should be enabled for user-owned tables and Storage policies should not grant unrestricted access.
- Signed URLs, if later needed for previews, should be generated by FastAPI with a short expiry.

### AI data boundary

- Only the data needed for extraction or matching should be sent to providers.
- Provider outputs are untrusted until Pydantic validation and business-rule reconciliation complete.
- AI output must not be presented as an official government determination.

## 16. Open architectural decisions

These decisions should be confirmed before implementation begins:

1. **Candidate profile cardinality:** use one active profile per user, or support multiple saved profiles?
2. **Authentication:** use Supabase email/password only, or add another provider later?
3. **Maximum PDF size:** use a 15 MB limit, or adjust for the project's sample notifications?
4. **Category values:** use `General`, `OBC`, `SC`, `ST`, `EWS`, and `PwD`, or extend the list for target notifications?
5. **Age reference date:** use the notification's stated date; if absent, use the check date or require verification?
6. **Processing mode:** run processing synchronously for the micro-project, or add a later polling-based job state without introducing a queue?
7. **Reprocessing policy:** overwrite the latest extraction, or retain all extraction versions?
8. **Provider model selection:** which Gemini PDF document processing and Gemini models will be used in the deployment environment?
9. **Source references:** rely on OCR-provided page boundaries only, or add a PDF viewer and page navigation later?
10. **Deployment:** select the hosting providers for the React frontend and FastAPI backend.
11. **Retention and deletion:** define how long uploaded PDFs, OCR text, profiles, and eligibility results are retained and how a user can delete them.
12. **Evaluation set:** select representative sample notifications and define how extraction, criterion classification, and `NEEDS_VERIFICATION` behavior will be evaluated.

