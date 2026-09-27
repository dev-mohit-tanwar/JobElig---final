from datetime import datetime, timezone
from uuid import UUID, uuid4

from google.genai import errors as genai_errors
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.services import job_service
from app.services import gemini
from app.schemas.document import DocumentExtraction, DocumentPage


USER_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ID = UUID("22222222-2222-2222-2222-222222222222")


def job_record(job_id: UUID, user_id: UUID = USER_ID, **overrides):
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(job_id),
        "user_id": str(user_id),
        "title": "Test notification",
        "organization": "Test organization",
        "original_filename": "notice.pdf",
        "storage_path": f"{user_id}/{job_id}/notice.pdf",
        "file_size": 9,
        "mime_type": "application/pdf",
        "processing_status": "OCR_COMPLETED",
        "page_count": 2,
        "ocr_text": '[{"page": 1, "markdown": "Page one"}]',
        "processing_error": None,
        "created_at": now,
        "updated_at": now,
    }
    record.update(overrides)
    return record


def auth_override():
    return AuthenticatedUser(id=str(USER_ID), email="user@example.com")


def setup_auth():
    app.dependency_overrides[get_current_user] = auth_override


def teardown_auth():
    app.dependency_overrides.clear()


def test_upload_requires_authentication():
    teardown_auth()
    response = TestClient(app).post(
        "/api/v1/jobs",
        files={"file": ("notice.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert response.status_code == 401


def test_missing_file_is_rejected():
    setup_auth()
    try:
        response = TestClient(app).post("/api/v1/jobs")
        assert response.status_code == 400
    finally:
        teardown_auth()


def test_non_pdf_is_rejected():
    setup_auth()
    try:
        response = TestClient(app).post(
            "/api/v1/jobs",
            files={"file": ("notice.txt", b"not a pdf", "text/plain")},
        )
        assert response.status_code == 400
    finally:
        teardown_auth()


def test_oversized_pdf_is_rejected(monkeypatch):
    setup_auth()
    monkeypatch.setattr(job_service, "MAX_FILE_SIZE", 4)
    try:
        response = TestClient(app).post(
            "/api/v1/jobs",
            files={"file": ("notice.pdf", b"%PDF-123", "application/pdf")},
        )
        assert response.status_code == 413
    finally:
        teardown_auth()


def test_authenticated_upload_uses_server_ownership_and_safe_path(monkeypatch):
    setup_auth()
    captured = {}

    def fake_process(user, content, filename, title, organization):
        captured.update(
            user=user,
            content=content,
            filename=filename,
            title=title,
            organization=organization,
        )
        return job_record(uuid4(), title=title, organization=organization)

    monkeypatch.setattr(job_service, "create_and_process", fake_process)
    try:
        response = TestClient(app).post(
            "/api/v1/jobs",
            data={"title": "Notice", "organization": "Board", "user_id": str(OTHER_ID)},
            files={"file": ("../../unsafe name.pdf", b"%PDF-1.7", "application/pdf")},
        )
        assert response.status_code == 201
        assert captured["user"].id == str(USER_ID)
        assert captured["filename"] == "../../unsafe name.pdf"
        assert "user_id" not in response.json()
        assert "storage_path" not in response.json()
    finally:
        teardown_auth()


def test_job_and_ocr_are_owner_scoped(monkeypatch):
    setup_auth()
    job_id = uuid4()
    monkeypatch.setattr(
        job_service,
        "read_job",
        lambda user, requested_id: job_record(requested_id)
        if user.id == str(USER_ID)
        else None,
    )
    monkeypatch.setattr(
        job_service,
        "read_ocr",
        lambda user, requested_id: {
            "job_id": requested_id,
            "page_count": 1,
            "pages": [{"page": 1, "markdown": "OCR"}],
        }
        if user.id == str(USER_ID)
        else None,
    )
    try:
        client = TestClient(app)
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200
        assert client.get(f"/api/v1/jobs/{job_id}/ocr").json()["pages"][0]["page"] == 1
    finally:
        teardown_auth()


def test_list_jobs_is_authenticated_owner_scoped_newest_first_and_lightweight(monkeypatch):
    setup_auth()
    newest = job_record(uuid4(), created_at="2026-09-25T12:00:00+00:00")
    oldest = job_record(uuid4(), created_at="2026-09-24T12:00:00+00:00")
    other_user_job = job_record(uuid4(), user_id=OTHER_ID, created_at="2026-09-26T12:00:00+00:00")
    captured = {}

    class Query:
        def select(self, fields):
            captured["fields"] = fields
            return self

        def eq(self, field, value):
            captured["owner"] = (field, value)
            return self

        def order(self, field, desc=False):
            captured["order"] = (field, desc)
            return self

        def execute(self):
            data = [newest, oldest, other_user_job]
            if captured["owner"] == ("user_id", str(USER_ID)):
                data = [item for item in data if item["user_id"] == str(USER_ID)]
            return type("Response", (), {"data": data})()

    class Client:
        def table(self, name):
            assert name == "job_notifications"
            return Query()

    monkeypatch.setattr(job_service, "get_supabase_client", lambda: Client())
    try:
        response = TestClient(app).get("/api/v1/jobs")
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body] == [newest["id"], oldest["id"]]
        assert other_user_job["id"] not in [item["id"] for item in body]
        assert captured["owner"] == ("user_id", str(USER_ID))
        assert captured["order"] == ("created_at", True)
        assert "storage_path" not in body[0]
        assert "ocr_text" not in body[0]
        assert "file_size" not in body[0]
    finally:
        teardown_auth()


def test_list_jobs_requires_authentication():
    teardown_auth()
    response = TestClient(app).get("/api/v1/jobs")
    assert response.status_code == 401


def test_delete_owned_job_removes_storage_and_record(monkeypatch):
    setup_auth()
    job_id = uuid4()
    calls = []

    class Query:
        def select(self, *_):
            self.is_duplicate_check = True
            return self

        def delete(self):
            calls.append("delete")
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def execute(self):
            return type("Response", (), {"data": [job_record(job_id)]})()

    class Bucket:
        def remove(self, paths):
            calls.append(("remove", paths))

    class Storage:
        def from_(self, name):
            assert name == job_service.BUCKET
            return Bucket()

    class Client:
        storage = Storage()

        def table(self, name):
            assert name == "job_notifications"
            return Query()

    monkeypatch.setattr(job_service, "get_supabase_client", lambda: Client())
    try:
        response = TestClient(app).delete(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 204
        assert calls[0][0] == "remove"
        assert calls[-1] == "delete"
    finally:
        teardown_auth()


def test_delete_other_users_job_is_not_found(monkeypatch):
    setup_auth()
    monkeypatch.setattr(job_service, "_get_job", lambda *_: None)
    try:
        assert TestClient(app).delete(f"/api/v1/jobs/{uuid4()}").status_code == 404
    finally:
        teardown_auth()


def test_duplicate_pdf_is_rejected_for_same_user(monkeypatch):
    existing = job_record(uuid4())

    class Query:
        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def execute(self):
            return type("Response", (), {"data": [existing]})()

    class Client:
        def table(self, name):
            assert name == "job_notifications"
            return Query()

    monkeypatch.setattr(job_service, "get_supabase_client", lambda: Client())
    try:
        job_service.create_and_process(
            auth_override(), b"%PDF-1.7", "notice.pdf", None, None
        )
    except job_service.DuplicateJobError as exc:
        assert exc.job["id"] == existing["id"]
    else:
        raise AssertionError("duplicate PDF should be rejected")


def test_other_user_job_is_not_returned(monkeypatch):
    setup_auth()
    monkeypatch.setattr(job_service, "read_job", lambda user, job_id: None)
    try:
        assert TestClient(app).get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    finally:
        teardown_auth()


def test_ocr_success_normalizes_pages_and_sets_status(monkeypatch):
    class Query:
        def __init__(self, response):
            self.response = response

        def insert(self, payload):
            self.inserted = payload
            return self

        def update(self, payload):
            self.updated = payload
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def select(self, *_):
            self.response = type("Response", (), {"data": []})()
            return self

        def execute(self):
            return self.response

    class StorageBucket:
        def upload(self, path, content, options):
            self.path = path
            self.content = content
            return {"path": path}

    class Storage:
        def __init__(self):
            self.bucket = StorageBucket()

        def from_(self, _):
            return self.bucket

    class Client:
        def __init__(self):
            self.storage = Storage()
            self.queries = []

        def table(self, _):
            query = Query(type("Response", (), {"data": [job_record(uuid4())]})())
            self.queries.append(query)
            return query

    client = Client()
    monkeypatch.setattr(job_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(
        job_service,
        "extract_document",
        lambda content, filename: [
            {"page": 1, "markdown": "# First"},
            {"page": 2, "markdown": "| table |"},
        ],
    )
    result = job_service.create_and_process(
        auth_override(), b"%PDF-1.7", "../../unsafe name.pdf", None, None
    )
    assert result["processing_status"] == "OCR_COMPLETED"
    assert result["page_count"] == 2
    assert client.storage.bucket.path.startswith(f"{USER_ID}/")
    assert client.storage.bucket.path.endswith("/unsafe_name.pdf")


def test_ocr_failure_marks_job_failed(monkeypatch):
    updates = []

    class Query:
        def select(self, *_):
            self.is_duplicate_check = True
            return self

        def insert(self, _):
            return self

        def update(self, payload):
            updates.append(payload)
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def execute(self):
            if getattr(self, "is_duplicate_check", False):
                return type("Response", (), {"data": []})()
            return type("Response", (), {"data": [job_record(uuid4())]})()

    class Client:
        def table(self, _):
            return Query()

        class Storage:
            def from_(self, _):
                return self

            def upload(self, *_):
                return {}

        storage = Storage()

    monkeypatch.setattr(job_service, "get_supabase_client", lambda: Client())
    monkeypatch.setattr(
        job_service,
        "extract_document",
        lambda *_: (_ for _ in ()).throw(RuntimeError("provider failure")),
    )
    try:
        job_service.create_and_process(
            auth_override(), b"%PDF-1.7", "notice.pdf", None, None
        )
    except job_service.JobServiceError:
        pass
    assert any(update.get("processing_status") == "FAILED" for update in updates)
    assert all("provider failure" not in str(update) for update in updates)


def test_ocr_failure_logs_failed_status_update_error(monkeypatch, caplog):
    record = job_record(uuid4())

    class StorageBucket:
        def upload(self, *_):
            return {}

    class Storage:
        def from_(self, _):
            return StorageBucket()

    class Client:
        storage = Storage()

        def table(self, _):
            return self

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def insert(self, *_):
            return self

        def execute(self):
            return type("Response", (), {"data": []})()

    monkeypatch.setattr(job_service, "get_supabase_client", lambda: Client())
    monkeypatch.setattr(job_service, "_update", lambda job_id, values, user_id: (
        (_ for _ in ()).throw(RuntimeError("status update outage"))
        if values.get("processing_status") == "FAILED"
        else record
    ))
    monkeypatch.setattr(
        job_service,
        "extract_document",
        lambda *_: (_ for _ in ()).throw(RuntimeError("provider failure")),
    )
    with caplog.at_level("ERROR", logger="app.services.job_service"):
        try:
            job_service.create_and_process(
                auth_override(), b"%PDF-1.7", "notice.pdf", None, None
            )
        except job_service.JobServiceError as exc:
            assert str(exc) == "Notification processing failed."
        else:
            raise AssertionError("processing failure should propagate")
    assert "job_id=" in caplog.text
    assert "provider failure" in caplog.text
    assert "status update outage" in caplog.text


def test_gemini_document_extraction_preserves_page_content(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            assert kwargs["model"]
            assert kwargs["contents"][0].inline_data.mime_type == "application/pdf"
            return type(
                "Response",
                (),
                {
                    "parsed": DocumentExtraction(
                        pages=[
                            DocumentPage(page=1, content="first"),
                            DocumentPage(page=2, content="table"),
                        ]
                    )
                },
            )()

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    assert gemini.extract_document(b"%PDF-1.7", "notice.pdf") == [
        {"page": 1, "markdown": "first"},
        {"page": 2, "markdown": "table"},
    ]


def test_gemini_document_extraction_rejects_malformed_output(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            return type("Response", (), {"parsed": {"pages": []}})()

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    try:
        gemini.extract_document(b"%PDF-1.7", "notice.pdf")
    except gemini.GeminiDocumentError as exc:
        assert str(exc) == "Gemini returned invalid document output."
    else:
        raise AssertionError("malformed document output should fail")


def test_gemini_document_extraction_handles_unavailable_provider(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            raise genai_errors.ServerError(
                503,
                {
                    "error": {
                        "status": "UNAVAILABLE",
                        "message": "temporary provider outage",
                    }
                },
            )

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    try:
        gemini.extract_document(b"%PDF-1.7", "notice.pdf")
    except gemini.GeminiUnavailableError as exc:
        assert str(exc) == "Gemini document processing is temporarily unavailable."
    else:
        raise AssertionError("503 provider outage should be classified as unavailable")


def test_gemini_document_extraction_handles_normal_provider_error(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            raise genai_errors.ServerError(
                500,
                {"error": {"status": "INTERNAL", "message": "provider failure"}},
            )

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    try:
        gemini.extract_document(b"%PDF-1.7", "notice.pdf")
    except gemini.GeminiDocumentError as exc:
        assert type(exc) is gemini.GeminiDocumentError
        assert str(exc) == "Gemini document processing failed."
    else:
        raise AssertionError("normal provider error should fail safely")


def test_gemini_document_diagnostic_is_sanitized_and_stage_aware(monkeypatch, caplog):
    secret = "test-gemini-secret"
    monkeypatch.setattr(gemini.settings, "gemini_api_key", SecretStr(secret))

    class Models:
        def generate_content(self, **kwargs):
            raise genai_errors.ServerError(
                500,
                {
                    "error": {
                        "status": "INTERNAL",
                        "message": f"provider failure {secret}",
                    }
                },
            )

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    with caplog.at_level("WARNING", logger="app.services.gemini"):
        try:
            gemini.extract_document(b"%PDF-1.7", "notice.pdf")
        except gemini.GeminiDocumentError as exc:
            assert str(exc) == "Gemini document processing failed."
        else:
            raise AssertionError("provider error should fail safely")

    diagnostic = caplog.text
    assert "exception_type=ServerError" in diagnostic
    assert "http_status=500" in diagnostic
    assert "provider_status=INTERNAL" in diagnostic
    assert "provider_message=provider failure [REDACTED]" in diagnostic
    assert "stage=generate_content" in diagnostic
    assert secret not in diagnostic
