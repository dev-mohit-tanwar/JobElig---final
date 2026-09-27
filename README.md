# JobEligAI

[Click here to run demo](https://dev-mohit-tanwar.github.io/JobElig---final/)

JobEligAI is a full-stack application designed to help a user assess whether a candidate appears to meet eligibility requirements for a public-sector recruitment notification. The system accepts a PDF recruitment notice, converts it into structured information, compares it with a candidate profile, and returns eligibility status with explanations and source references.

This project is built as a practical micro-project combining:

- React frontend for user interaction
- FastAPI backend for business logic and secure API access
- Supabase for authentication, persistence, and storage
- Google Gemini for PDF document extraction and structured analysis

The project focuses on explainability and conservative decision-making: it does not blindly trust AI, and it validates extracted facts before using them in any final result.

---

## 1. Project goal

The core idea is simple:

1. A user uploads a recruitment PDF.
2. The backend extracts the document text while preserving page boundaries.
3. AI converts the raw text into structured eligibility criteria.
4. The user fills in their candidate profile.
5. The backend compares the job requirements with the profile.
6. A result is produced: eligible, not eligible, or needs verification.

The application is meant to act as an assistive tool, not an official government decision-maker. The original notification remains the authority, and the app explains how it reached a conclusion.

---

## 2. High-level architecture

```text
Browser / React App
        |
        | HTTPS + JWT bearer token
        v
FastAPI Backend
        |
        +--> Supabase Auth (user identity validation)
        +--> Supabase PostgreSQL (saved data)
        +--> Supabase Storage (uploaded PDFs)
        +--> Gemini API (PDF extraction + eligibility interpretation)
        +--> Pydantic validation (schema enforcement)
        v
Eligibility, Matching, and Results
```

The design intentionally keeps the backend as the orchestration layer. The frontend never calls Gemini directly, never stores service secrets, and never performs final decision logic by itself.

---

## 3. Tech stack

### Frontend

- React
- Vite
- React Router
- Plain CSS / component-based UI
- Supabase JS client for authentication session

### Backend

- Python
- FastAPI
- Pydantic + Pydantic Settings
- Python multipart uploads
- JWT-based auth via Supabase

### Data and storage

- Supabase PostgreSQL
- Supabase Storage
- Supabase Auth

### AI / document processing

- Google Gemini API
- Gemini PDF document processing for page-aware extraction
- Structured JSON validation using Pydantic schemas

### Dev and testing tools

- pytest
- uvicorn
- python-dotenv style environment handling through settings classes

---

## 4. Project structure

```text
jobelige/
├── .gitignore
├── README.md
├── backend/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── health.py
│   │   │       ├── jobs.py
│   │   │       └── profile.py
│   │   ├── dependencies/
│   │   │   ├── __init__.py
│   │   │   └── auth.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── eligibility.py
│   │   │   ├── health.py
│   │   │   ├── job.py
│   │   │   ├── matching.py
│   │   │   └── profile.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── gemini.py
│   │   │   ├── job_service.py
│   │   │   ├── matching_service.py
│   │   │   ├── profile_service.py
│   │   │   └── supabase_client.py
│   │   └── utils/
│   │       └── __init__.py
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── check_supabase.py
│   │   └── diagnose_gemini_pdf.py
│   └── tests/
│       ├── __init__.py
│       ├── test_phase3_api.py
│       ├── test_phase4_jobs.py
│       ├── test_phase5_gemini.py
│       └── test_phase6_matching.py
├── frontend/
│   ├── .env
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── styles.css
│   │   └── lib/
│   │       ├── api.js
│   │       └── supabase.js
├── database/
│   └── migrations/
│       ├── 0001_initial_schema.sql
│       └── 0002_job_file_hash.sql
├── docs/
│   ├── architecture.md
│   └── database.md
└── .kilo/ (removed from final repo; kept only in earlier worktree metadata)
```

---

## 5. Core application flow

### A. User authentication

- The user signs in through Supabase Auth in the frontend.
- The frontend receives a Supabase JWT.
- Every protected API request attaches the token as a bearer token.
- The backend verifies that token in `app.dependencies.auth`.
- The user object is then used to scope all data access to that specific user.

### B. Candidate profile creation

- The user opens the profile screen in React.
- They enter details such as date of birth, category, degree, branch, percentage, CGPA, experience, certifications, and nationality.
- The frontend sends the profile payload to the FastAPI profile endpoints.
- The backend validates the schema and stores the profile for the authenticated user.

This keeps profile data tied to the correct account and avoids mixing user profiles across accounts.

### C. PDF upload and job creation

- The user uploads a job notification PDF.
- The backend validates that it is a PDF and under the allowed size limit.
- The job is created and ownership is assigned to the current user.
- The PDF is queued for processing and the backend begins the document extraction pipeline.

### D. OCR / document extraction

- The PDF is sent to Gemini PDF document processing.
- The model returns page-aware text with actual page numbers.
- The backend stores the extracted OCR text and page information.
- Source references preserve page numbers, which is important for explaining results later.

### E. Eligibility extraction

- Once the OCR text is available, the backend sends it to Gemini with an instruction to extract structured eligibility facts.
- Output fields may include:
  - job title
  - organization
  - posts and vacancies
  - degree and branch requirements
  - percentage / CGPA thresholds
  - age limits
  - category requirements
  - experience requirements
  - certifications
  - nationality rules
  - other requirements and uncertainties

The backend validates all AI output using Pydantic schemas before storing or using it.

### F. Matching against the candidate profile

- The backend loads the user's profile and the notification's extracted criteria.
- It runs deterministic checks using Python where the logic is numeric or binary.
- It then sends candidate and eligibility data to Gemini for semantic interpretation.
- Gemini proposes criterion-by-criterion statuses such as:
  - PASS
  - FAIL
  - NEEDS_VERIFICATION
  - NOT_APPLICABLE

The final result is conservative and reconciled to avoid false positives.

---

## 6. Detailed data flow

The actual flow in this project follows this sequence:

1. React app loads auth session using Supabase.
2. User logs in or signs up.
3. User uploads a recruitment PDF from the frontend.
4. FastAPI verifies the bearer token and authorizes the user.
5. The upload is validated for type and size.
6. The backend stores job metadata and file details.
7. Gemini extracts page-aware document content.
8. The extracted text is structured into recruitment facts.
9. The user saves their profile in the backend.
10. FastAPI reads both the notification and the profile.
11. Deterministic Python checks run for age, CGPA, marks, experience, etc.
12. Matching service compares the candidate against the extracted criteria.
13. Gemini provides semantic explanations and remaining ambiguous items.
14. The backend validates and reconciles outputs.
15. A final result is generated and shown in the UI.

This is the key design principle of the project: deterministic checks remain in Python, while nuanced human-language interpretation is delegated to Gemini with guardrails.

---

## 7. Main backend components

### `app.main`

This is the FastAPI application entry point. It registers CORS and includes the API routers.

### `app.config`

Loads environment variables using `pydantic-settings`, including:

- `APP_NAME`
- `ENVIRONMENT`
- `ALLOWED_ORIGINS`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`

This is where the project centralizes its backend configuration.

### `app.dependencies.auth`

This verifies the bearer token and extracts the current user identity from Supabase. Every protected route depends on it.

### `app.api.routes.jobs`

Handles:

- job listing
- PDF upload
- OCR fetching
- processing requests
- eligibility retrieval
- matching execution

### `app.api.routes.profile`

Handles candidate profile creation, updating, reading, and deletion.

### `app.api.routes.auth`

Exposes the identity endpoint to fetch the current logged-in user.

### `app.services.gemini`

Contains the provider logic for:

- PDF extraction
- recruitment summary generation
- eligibility extraction
- semantic matching

This module validates and sanitizes provider output carefully, including redacting secrets from logs.

### `app.services.job_service`

Responsible for job lifecycle logic, such as:

- checking duplicate uploads
- validating PDF contents
- creating notification records
- processing and storing OCR output
- retrieving eligibility data

### `app.services.matching_service`

Responsible for candidate-to-job matching and the final eligibility result generation.

### `app.services.profile_service`

Handles profile persistence and validation for the signed-in user.

### `app.services.supabase_client`

Creates the Supabase client used for storage and auth operations.

---

## 8. Frontend architecture

The frontend is a single-page React app with route-driven screens. It is designed to be session-driven and service-agnostic: it uses Supabase for auth, but all serious business logic lives in FastAPI.

### Important frontend files

- `frontend/src/App.jsx` — main app, routes, auth flow, profile form, upload workflow, matching screens
- `frontend/src/lib/api.js` — wrapper for authenticated requests to the backend
- `frontend/src/lib/supabase.js` — Supabase client initialization for browser auth

### Frontend responsibilities

- sign in / sign out
- session persistence
- profile form update
- recruitment PDF upload
- showing file and processing states
- displaying extracted info and results
- calling protected FastAPI endpoints with bearer tokens

### Frontend does not do

- no direct Gemini calls
- no service-role Supabase key usage
- no direct application DB writes
- no final business logic independent of backend validation

---

## 9. API and route overview

The backend exposes the most important routes under `/api/v1` and includes an auth dependency on each secure endpoint.

### Auth routes

- `GET /api/v1/auth/me` — returns the current user identity

### Profile routes

- `GET /api/v1/profile` — read current profile
- `POST /api/v1/profile` — create profile
- `PUT /api/v1/profile` — update profile
- `DELETE /api/v1/profile` — delete profile

### Job routes

- `GET /api/v1/jobs` — list notifications for the current user
- `POST /api/v1/jobs` — upload and create a new job notification
- `GET /api/v1/jobs/{job_id}` — get one job
- `GET /api/v1/jobs/{job_id}/ocr` — read OCR extraction
- `POST /api/v1/jobs/{job_id}/process` — process notification through the extraction pipeline
- `GET /api/v1/jobs/{job_id}/eligibility` — returns extracted eligibility data
- `POST /api/v1/jobs/{job_id}/match` — run candidate matching
- `GET /api/v1/jobs/{job_id}/match` — fetch the latest eligibility result

### Health route

- `GET /health` — general backend health check

---

## 10. Environment setup

### Backend environment

Create a backend `.env` file based on the project example, with the required values for Supabase and Gemini.

Example:

```env
APP_NAME=JobEligAI API
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:5173
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-supabase-service-role-secret
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-3-flash-preview
```

Important:

- `SUPABASE_SECRET_KEY` stays on the backend only.
- `GEMINI_API_KEY` stays on the backend only.
- `ALLOWED_ORIGINS` must include the frontend URL.

### Frontend environment

The frontend uses browser-safe variables:

```env
VITE_API_BASE_URL=http://127.0.0.1:8002
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-public-anon-key
```

The frontend should never receive the service-role secret or Gemini key.

---

## 11. Local development steps

### 1. Backend setup

```powershell
cd "C:\Users\mohit\Downloads\jobelige\jobelige\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

The API is expected at:

- http://127.0.0.1:8002

### 2. Frontend setup

```powershell
cd "C:\Users\mohit\Downloads\jobelige\jobelige\frontend"
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

The Vite server usually runs at:

- http://localhost:5173

---

## 12. How the matching logic works

The project uses a hybrid approach instead of fully trusting one single model.

### Deterministic checks

The backend performs direct Python checks for structured values such as:

- age vs minimum age
- age vs maximum age
- percentage thresholds
- CGPA thresholds
- experience thresholds
- graduation-year requirements

If the comparison is well-defined and valid, Python is treated as the authoritative result.

### AI-assisted semantic checks

Gemini handles interpretation of natural language, such as:

- branch equivalence
- degree equivalence
- special-case exceptions
- ambiguous wording
- contextual interpretation of recruitment language

The result is validated and conservative. If the machine output is uncertain or contradictory, the app prefers a `NEEDS_VERIFICATION` outcome rather than a forced pass.

This helps reduce incorrect automated eligibility decisions.

---

## 13. Important design decisions

### Conservative eligibility policy

The system is designed to avoid false positives.

- A clear fail on a required criterion leads to `NOT_ELIGIBLE`.
- Missing or ambiguous requirements lead to `NEEDS_VERIFICATION`.
- `ELIGIBLE` is only used when enough facts are clearly established.

### Security by default

- JWTs are required for protected API routes.
- User data access is limited to the authenticated owner.
- Secrets remain server-side.
- PDF uploads are checked before processing.

### Explainability over hidden AI decisions

The app is not just returning a final verdict. It is storing and surfacing:

- required values
- candidate values
- explanations
- missing facts
- source page references
- uncertainty markers

---

## 14. Data model focus

The project is centered around a few core entities:

### Candidate profile

Stores the user's personal and academic details, such as:

- full name
- date of birth
- category
- degree and branch
- percentage / CGPA
- graduation year
- experience
- certifications
- nationality

### Job notification

Represents a recruitment PDF uploaded by the user. It tracks:

- owner
- title
- organization
- file metadata
- processing status
- OCR text
- page count
- summary
- error state

### Eligibility extraction

Stores the structured representation of a recruitment notification extracted by Gemini.

### Eligibility result

Stores a time-based evaluation of a specific notification against a candidate profile.

### Criterion result

Stores each individual eligibility criterion result and its explanation.

---

## 15. Status and testing approach

The repository includes tests under `backend/tests` for a staged implementation. These are aimed at:

- API behavior
- job lifecycle handling
- Gemini extraction and validation
- matching logic

Example test areas:

- `test_phase3_api.py`
- `test_phase4_jobs.py`
- `test_phase5_gemini.py`
- `test_phase6_matching.py`

The project follows a phased approach, where the backend capabilities are built and validated in stages rather than as a single monolithic commit.

---

## 16. Non-functional goals

This project is designed to be:

- easy to understand for academic use
- modular enough for future extension
- safe around user-owned data
- grounded in deterministic logic plus AI-assisted reasoning
- transparent about uncertainty and missing information

---

## 17. Future improvement ideas

This application is a strong base for several future enhancements:

- better PDF viewer integration
- stronger result caching
- bulk job history and filtering
- richer eligibility criteria mapping
- improved front-end dashboards
- support for more recruitment categories and edge cases
- role-based admin or moderation workflows

---

## 18. Summary

JobEligAI is a practical AI-assisted recruitment eligibility checker built around:

- a secure React frontend
- a FastAPI backend
- Supabase authentication and storage
- Google Gemini-based document extraction and matching
- conservative rule validation and explainability

Its key value is not simply a yes/no answer; it is the ability to explain why a candidate may or may not meet a requirement, using source-backed evidence and clear result states.

If you are running this project locally, the normal development flow is:

1. configure backend and frontend env files
2. install dependencies
3. start FastAPI
4. start the React app
5. sign in with Supabase
6. upload a PDF
7. fill in the candidate profile
8. process the notification and view eligibility results

---

## Quick start

```bash
# backend
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002

# frontend
cd frontend
npm install
npm run dev
```

---

## Notes

This repository includes both implementation code and project documentation. The document in `docs/architecture.md` provides deeper architectural context, while this README gives the practical overview for setup, usage, and understanding the project as a whole.
