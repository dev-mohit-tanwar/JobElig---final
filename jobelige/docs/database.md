# JobEligAI Database and Storage

## Scope and migration

Phase 2 defines the reproducible Supabase database and private PDF Storage configuration. The single migration is:

`supabase/migrations/0001_initial_schema.sql`

The migration is applied to the linked Supabase project. Its remote history was verified with `supabase migration list --linked`, which reports local and remote version `0001`.

This migration does not include application code or authentication UI. The current
implementation uses it through Phase 5 for upload, OCR, Gemini extraction, and
versioned eligibility storage.

## Phase 3 backend access

Supabase Auth remains the identity provider. The browser sends an access token as:

```text
Authorization: Bearer <Supabase access token>
```

FastAPI's `get_current_user` dependency validates that token through the server-side Supabase client and exposes only the authenticated user's ID and email to protected routes. FastAPI derives `user_id` from that identity; clients cannot choose an ownership ID.

The backend uses `SUPABASE_URL` and `SUPABASE_SECRET_KEY` from `backend/.env`. The secret key is never sent to React, returned by an endpoint, or logged. Because the privileged client bypasses database RLS, profile routes also explicitly filter operations by the authenticated user's ID.

Candidate profile endpoints:

- `GET /api/v1/profile` - return the authenticated user's profile.
- `POST /api/v1/profile` - create the user's single active profile; duplicate creation returns `409`.
- `PUT /api/v1/profile` - update only the authenticated user's profile.
- `DELETE /api/v1/profile` - delete only the authenticated user's profile.
- `GET /api/v1/auth/me` - return the authenticated user's ID and email.

Missing, malformed, or expired bearer tokens return `401`. Missing owned profiles return `404`. Invalid profile payloads return `422`, and database failures are returned as safe generic errors without SQL or stack traces.

## Phase 4 recruitment notifications and OCR

Authenticated clients upload PDFs through `POST /api/v1/jobs` using multipart form data. Optional `title` and `organization` fields are accepted. The backend requires `Authorization: Bearer <Supabase access token>`, validates the `application/pdf` MIME type, checks the `%PDF-` file signature, and rejects files larger than 15 MB.

Each accepted file creates a notification owned by the authenticated user. The backend, not the client, generates the job UUID and stores the file in the existing private bucket at:

```text
<user_id>/<job_id>/<safe_filename>.pdf
```

The client cannot provide `user_id` or `storage_path`. Filenames are reduced to a safe basename before storage. The bucket remains private and no public or permanent URL is returned.

The synchronous Phase 4 processing flow is:

```text
UPLOADED -> PROCESSING -> OCR_COMPLETED
```

If Storage or Gemini processing fails, the job is updated to `FAILED` with a safe generic processing error. The original private object is retained after an OCR failure for later retry/inspection. The job is never marked `COMPLETED` or `EXTRACTION_COMPLETED` in this phase.

Gemini PDF document processing uses the server-only `Gemini_API_KEY` and model `Gemini-ocr-latest`. The installed SDK returns zero-based page `index` values; the provider index is normalized to one-based page records and serialized as JSON in `job_notifications.ocr_text`, preserving page boundaries and Markdown:

```json
[
  {"page": 1, "markdown": "..."},
  {"page": 2, "markdown": "..."}
]
```

The endpoints are:

- `POST /api/v1/jobs` - upload, store, and synchronously OCR a PDF.
- `GET /api/v1/jobs/{job_id}` - return owner-scoped notification metadata and status without OCR text or Storage URLs.
- `GET /api/v1/jobs/{job_id}/ocr` - return owner-scoped page-preserving OCR content.

Only FastAPI uses `Gemini_API_KEY` and `SUPABASE_SECRET_KEY`; neither secret is exposed to React or returned in API responses. Phase 4 itself ended before Gemini analysis; Phase 5 adds summaries and eligibility extraction but not matching or eligibility decisions.

## Phase 5 Gemini analysis

`POST /api/v1/jobs/{job_id}/process` is an authenticated, owner-scoped endpoint
that consumes the page-preserving JSON already stored in `ocr_text`. The original
PDF is not sent to Gemini. The backend uses the official `google-genai` Python SDK
with a server-only `GEMINI_API_KEY` and requests JSON matching the Pydantic
summary/extraction schema. Document text is treated as untrusted data; Gemini has
no tools, filesystem, database, or browsing access.

The processing flow is:

```text
OCR_COMPLETED -> PROCESSING -> COMPLETED
                         \-> FAILED
```

The factual summary is stored in `job_notifications.summary`. The validated
eligibility object is stored in `extracted_eligibility.eligibility_json`, with a
new version selected from existing records so `(job_id, version)` remains unique.
Source references preserve page numbers and snippets only when supported by OCR.
Missing values remain null/empty and ambiguous wording is recorded in uncertainty.

`GET /api/v1/jobs/{job_id}/eligibility` returns the latest successful,
owner-scoped extraction. Candidate matching and final decisions are handled by
the Phase 6 endpoints below.

## Phase 6 candidate matching

Phase 6 adds:

- `POST /api/v1/jobs/{job_id}/match` to create a new owner-scoped matching result.
- `GET /api/v1/jobs/{job_id}/match` to retrieve the latest owner-scoped result.

The backend loads the authenticated user's existing candidate profile and the
latest successful eligibility extraction. Python evaluates objective age,
percentage, CGPA, explicit numeric experience, nationality, and category rules.
Only degree/branch interpretation, certifications, complex experience, and other
textual criteria are sent to Gemini. The Gemini response is structured JSON
validated with Pydantic and cannot override a deterministic failure.

Every evaluated criterion is persisted in `criterion_results`; the overall
conservative result is persisted in `eligibility_results`. Missing or ambiguous
information produces `NEEDS_VERIFICATION`. Re-running matching inserts a new
eligibility result and criterion set. No schema change was required.

## Application tables

### `candidate_profiles`

Stores one active profile per user. Important columns are:

- `id` - UUID primary key.
- `user_id` - UUID foreign key to `auth.users(id)`, unique.
- `full_name`, `date_of_birth`, `category`, `degree`, `branch`, `nationality`.
- `percentage`, `cgpa`, `graduation_year`, `experience_years`.
- `certifications` - text array.
- `additional_information` - JSONB for extensible candidate fields.
- `created_at`, `updated_at` - timestamps.

The database checks percentage, CGPA, and experience ranges.

### `job_notifications`

Stores one uploaded recruitment notification:

- `id` - UUID primary key.
- `user_id` - UUID foreign key to `auth.users(id)`.
- `title`, `organization`, and `original_filename`.
- `storage_path` - private Storage object path.
- `file_size` and `mime_type`.
- `processing_status`.
- `page_count`, `ocr_text`, `summary`, and `processing_error`.
- `created_at`, `updated_at`.

Allowed processing statuses are `UPLOADED`, `PROCESSING`, `OCR_COMPLETED`, `EXTRACTION_COMPLETED`, `COMPLETED`, and `FAILED`. The database restricts files to `application/pdf` and 15 MB or less.

### `extracted_eligibility`

Stores versioned structured eligibility output:

- `id` - UUID primary key.
- `job_id` - foreign key to `job_notifications(id)`.
- `version` - positive extraction version.
- `eligibility_json` - JSONB source of truth for notification-specific requirements.
- `extraction_status`.
- `created_at`.

The JSONB can contain job title, organization, posts, vacancies, accepted degrees and branches, percentage/CGPA thresholds, age limits and relaxation, categories, experience, certifications, nationality, exceptions, uncertainty, and source references. A unique `(job_id, version)` constraint prevents duplicate versions.

### `eligibility_results`

Stores one candidate-versus-notification check:

- `id` - UUID primary key.
- `user_id` - foreign key to `auth.users(id)`.
- `job_id` - foreign key to `job_notifications(id)`.
- `candidate_profile_id` - foreign key to `candidate_profiles(id)`.
- `overall_status` - `ELIGIBLE`, `NOT_ELIGIBLE`, or `NEEDS_VERIFICATION`.
- `missing_information`, `warnings`, `final_explanation`.
- `matching_json` - JSONB audit output.
- `created_at`.

### `criterion_results`

Stores explainability rows for an eligibility result:

- `id` - UUID primary key.
- `eligibility_result_id` - foreign key to `eligibility_results(id)`.
- `criterion_name`, `status`, `candidate_value`, `required_value`.
- `explanation`, `source_reference`.
- `checking_method` - `DETERMINISTIC`, `GEMINI`, or `BOTH`.
- `display_order`, `created_at`.

Criterion statuses are `PASS`, `FAIL`, `NEEDS_VERIFICATION`, and `NOT_APPLICABLE`.

## Relationships

```text
auth.users
  â”œâ”€â”€ candidate_profiles
  â”œâ”€â”€ job_notifications
  â”‚     â””â”€â”€ extracted_eligibility
  â””â”€â”€ eligibility_results
        â”œâ”€â”€ candidate_profiles
        â”œâ”€â”€ job_notifications
        â””â”€â”€ criterion_results
```

All relationships use UUID foreign keys. Child records cascade when their owning parent is deleted. An eligibility result records the exact job and candidate profile used for the check.

## Application RLS policies

RLS is enabled on all five application tables. The migration removes and recreates the named policies, making the migration safe to rerun:

- `Users manage their own candidate profile` on `candidate_profiles`: `auth.uid() = user_id` for `USING` and `WITH CHECK`.
- `Users manage their own job notifications` on `job_notifications`: `auth.uid() = user_id` for `USING` and `WITH CHECK`.
- `Users read eligibility for their own jobs` on `extracted_eligibility`: a parent `job_notifications` row must have the same `job_id` and `user_id = auth.uid()`.
- `Users read their own eligibility results` on `eligibility_results`: `auth.uid() = user_id`.
- `Users read criteria for their own results` on `criterion_results`: a parent `eligibility_results` row must have `user_id = auth.uid()`.

There are no public application-data policies. The backend uses the server-only `SUPABASE_SECRET_KEY`, which has privileged access, but FastAPI must still enforce explicit ownership checks in application code.

## Storage bucket

The migration creates or updates the `recruitment-pdfs` bucket with:

- `public = false`.
- `file_size_limit = 15728640` bytes (15 MB).
- `allowed_mime_types = ['application/pdf']`.

The intended path is:

```text
<user_id>/<job_id>/original_filename.pdf
```

The migration does not alter, own, move, or modify the managed `storage.objects` table. Supabase's existing Storage RLS model is used; only policies are created.

## Verified Storage policies

The following policy definitions are present in the applied migration and match the deployed migration version:

### SELECT/read

Policy: `Users read their recruitment PDFs`

```sql
bucket_id = 'recruitment-pdfs'
and (storage.foldername(name))[1] = auth.uid()::text
```

This permits a user's authenticated Storage request to read only objects in the private bucket whose first path segment is that user's UUID. It therefore enforces the `user_id/job_id/original_filename.pdf` ownership boundary.

### INSERT/upload

Policy: `Users upload their recruitment PDFs`

```sql
bucket_id = 'recruitment-pdfs'
and (storage.foldername(name))[1] = auth.uid()::text
and lower(storage.extension(name)) = 'pdf'
```

This restricts inserts to the user's UUID-prefixed path and requires a `.pdf` extension. The bucket MIME configuration separately restricts the allowed MIME type to `application/pdf`.

### UPDATE

Policy: `Users update their recruitment PDFs`

Both `USING` and `WITH CHECK` require:

```sql
bucket_id = 'recruitment-pdfs'
and (storage.foldername(name))[1] = auth.uid()::text
```

This prevents a user from updating or moving an object outside their own UUID-prefixed path.

### DELETE

Policy: `Users delete their recruitment PDFs`

```sql
bucket_id = 'recruitment-pdfs'
and (storage.foldername(name))[1] = auth.uid()::text
```

This permits deletion only for objects in the user's own UUID-prefixed path.

All four policies rely on Supabase's authenticated request context through `auth.uid()`. No anonymous or public Storage policy is created.

## Verification record

The following Phase 2 checks were performed against the current project:

- `supabase migration list --linked` reports migration `0001` both locally and remotely.
- The backend Supabase check read `candidate_profiles` successfully.
- The backend Storage check found `recruitment-pdfs` and reported `public=False`.
- The applied migration contains the exact four Storage policy conditions documented above.
- The migration contains no `ALTER TABLE storage.objects`, ownership change, schema change, or column modification.
- The migration configures the bucket as private, PDF-only, and limited to 15 MB.

The policy SQL conditions are verified from the migration version confirmed in remote migration history. The live metadata check confirms the bucket's current privacy configuration and existence.

## Indexes

Only required query indexes are created:

- `idx_candidate_profiles_user_id`
- `idx_job_notifications_user_id`
- `idx_job_notifications_processing_status`
- `idx_extracted_eligibility_job_id`
- `idx_eligibility_results_user_id`
- `idx_eligibility_results_job_id`
- `idx_criterion_results_result_id`

## Backend secret boundary

The backend reads `SUPABASE_URL` and `SUPABASE_SECRET_KEY` from `backend/.env` through `pydantic-settings`. The secret key is wrapped as `SecretStr` and is used only by `backend/app/services/supabase_client.py`.

`backend/.env` is ignored by Git. `backend/.env.example` contains placeholders only. React must never receive or use `SUPABASE_SECRET_KEY`; it must communicate with FastAPI instead. FastAPI must not log the key and must validate the authenticated user's ownership even when using privileged Supabase access.

