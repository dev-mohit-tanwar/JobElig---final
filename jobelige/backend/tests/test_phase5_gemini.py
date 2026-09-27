import json
from uuid import UUID, uuid4

from google.genai import errors as genai_errors
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.schemas.eligibility import (
    EligibilityExtraction,
    GeminiAnalysis,
    PostEligibility,
    RecruitmentSummary,
    SourceReference,
)
from app.services import job_service
from app.services import gemini


USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def user():
    return AuthenticatedUser(id=str(USER_ID), email="user@example.com")


def job(job_id, **overrides):
    record = {
        "id": str(job_id),
        "user_id": str(USER_ID),
        "ocr_text": json.dumps([{"page": 1, "markdown": "Page one"}]),
        "processing_status": "OCR_COMPLETED",
    }
    record.update(overrides)
    return record


def analysis(page=1):
    post = PostEligibility(
        post_title="Junior Engineer",
        vacancies=3,
        accepted_degrees=["B.Tech"],
        accepted_branches=["Computer Science"],
        minimum_percentage=60,
        minimum_cgpa=6.5,
        age_max=30,
        source_references=[SourceReference(page=page, snippet="B.Tech")],
    )
    return GeminiAnalysis(
        summary=RecruitmentSummary(
            organization="Public Board",
            recruitment_title="Junior Engineer Recruitment",
            vacancies="3",
            qualifications=["B.Tech"],
            factual_summary="The notice recruits junior engineers.",
        ),
        eligibility=EligibilityExtraction(
            job_title="Junior Engineer",
            organization="Public Board",
            posts=[post],
        ),
    )


class Query:
    def __init__(self, data=None):
        self.data = data or []

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_):
        return self

    def insert(self, payload):
        self.inserted = payload
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def execute(self):
        return type("Response", (), {"data": self.data})()


class Client:
    def __init__(self, existing_versions=None):
        self.extraction = Query(
            [{"version": value} for value in (existing_versions or [])]
        )
        self.inserted = []

    def table(self, name):
        if name == "extracted_eligibility":
            query = self.extraction
            original_insert = query.insert

            def insert(payload):
                self.inserted.append(payload)
                return original_insert(payload)

            query.insert = insert
            return query
        return Query([{"id": "job"}])


def test_process_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).post(f"/api/v1/jobs/{uuid4()}/process")
    assert response.status_code == 401


def test_missing_ocr_is_rejected(monkeypatch):
    job_id = uuid4()
    monkeypatch.setattr(job_service, "_get_job", lambda *_: job(job_id, ocr_text=None))
    try:
        job_service.process_notification(user(), job_id)
    except job_service.JobServiceError as exc:
        assert str(exc) == "Notification has no OCR text."
    else:
        raise AssertionError("missing OCR should fail")


def test_success_stores_summary_eligibility_and_version(monkeypatch):
    job_id = uuid4()
    client = Client()
    updates = []
    monkeypatch.setattr(job_service, "_get_job", lambda *_: job(job_id))
    monkeypatch.setattr(job_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(job_service, "_update", lambda *_args, **kwargs: updates.append(
        _args[1]
    ) or {**job(job_id), **_args[1]})
    monkeypatch.setattr(job_service, "analyze_notification", lambda _: analysis())

    result = job_service.process_notification(user(), job_id)

    assert result["processing_status"] == "COMPLETED"
    assert client.inserted[0]["version"] == 1
    assert client.inserted[0]["eligibility_json"]["posts"][0]["minimum_cgpa"] == 6.5
    assert any(update.get("summary") for update in updates)


def test_reprocessing_uses_next_version(monkeypatch):
    job_id = uuid4()
    client = Client(existing_versions=[1])
    monkeypatch.setattr(job_service, "_get_job", lambda *_: job(job_id))
    monkeypatch.setattr(job_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(job_service, "_update", lambda *_args, **_kwargs: {
        **job(job_id), **_args[1]
    })
    monkeypatch.setattr(job_service, "analyze_notification", lambda _: analysis())

    job_service.process_notification(user(), job_id)

    assert client.inserted[0]["version"] == 2


def test_invalid_gemini_output_marks_failed(monkeypatch):
    job_id = uuid4()
    updates = []
    monkeypatch.setattr(job_service, "_get_job", lambda *_: job(job_id))
    monkeypatch.setattr(job_service, "_update", lambda *_args, **_kwargs: updates.append(
        _args[1]
    ) or {**job(job_id), **_args[1]})
    monkeypatch.setattr(
        job_service,
        "analyze_notification",
        lambda _: (_ for _ in ()).throw(
            job_service.GeminiAnalysisError("Gemini returned invalid structured output.")
        ),
    )

    try:
        job_service.process_notification(user(), job_id)
    except job_service.JobServiceError:
        pass
    assert any(update.get("processing_status") == "FAILED" for update in updates)
    assert any(
        "invalid structured output" in (update.get("processing_error") or "")
        for update in updates
    )


def test_source_page_not_in_ocr_is_rejected_without_storage(monkeypatch):
    job_id = uuid4()
    client = Client()
    monkeypatch.setattr(job_service, "_get_job", lambda *_: job(job_id))
    monkeypatch.setattr(job_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(job_service, "_update", lambda *_args, **_kwargs: {
        **job(job_id), **_args[1]
    })
    monkeypatch.setattr(job_service, "analyze_notification", lambda _: analysis(page=2))

    try:
        job_service.process_notification(user(), job_id)
    except job_service.JobServiceError as exc:
        assert "source references" in str(exc)
    assert not client.inserted


def test_analysis_provider_diagnostic_is_sanitized_and_stage_aware(monkeypatch, caplog):
    secret = "phase5-gemini-secret"
    monkeypatch.setattr(gemini.settings, "gemini_api_key", SecretStr(secret))

    class Models:
        def generate_content(self, **kwargs):
            raise genai_errors.ServerError(
                503,
                {
                    "error": {
                        "status": "UNAVAILABLE",
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
            gemini.analyze_notification("page content")
        except gemini.GeminiAnalysisError as exc:
            assert str(exc) == "Gemini analysis failed."
        else:
            raise AssertionError("provider error should fail safely")

    diagnostic = caplog.text
    assert "Gemini analysis diagnostic:" in diagnostic
    assert "exception_type=ServerError" in diagnostic
    assert "http_status=503" in diagnostic
    assert "provider_status=UNAVAILABLE" in diagnostic
    assert "provider_message=provider failure [REDACTED]" in diagnostic
    assert "model=gemini-3.5-flash" in diagnostic
    assert "stage=generate_content" in diagnostic
    assert secret not in diagnostic


def test_analysis_validation_diagnostic_identifies_pydantic_stage(monkeypatch, caplog):
    class Models:
        def generate_content(self, **kwargs):
            return type("Response", (), {"parsed": {"invalid": True}})()

    monkeypatch.setattr(
        gemini.genai,
        "Client",
        lambda **_: type("Client", (), {"models": Models()})(),
    )
    with caplog.at_level("WARNING", logger="app.services.gemini"):
        try:
            gemini.analyze_notification("page content")
        except gemini.GeminiAnalysisError as exc:
            assert str(exc) == "Gemini returned invalid structured output."
        else:
            raise AssertionError("invalid output should fail safely")

    assert "stage=pydantic_validation" in caplog.text


def test_multiple_posts_remain_distinct_and_unknown_values_are_null():
    first = PostEligibility(post_title="A", source_references=[SourceReference(page=1)])
    second = PostEligibility(post_title="B")
    extracted = EligibilityExtraction(posts=[first, second])
    assert [post.post_title for post in extracted.posts] == ["A", "B"]
    assert extracted.minimum_percentage is None


def test_extraction_version_conflict_retries_next_version():
    class ConflictQuery(Query):
        def __init__(self, owner):
            super().__init__([])
            self.owner = owner
            self.payload = None

        def execute(self):
            if hasattr(self, "inserted"):
                self.owner.insert_attempts += 1
                if self.owner.insert_attempts == 1:
                    raise RuntimeError(
                        "duplicate key value violates unique constraint "
                        "extracted_eligibility_job_id_version_key (23505)"
                    )
                self.data = [{"version": self.inserted["version"]}]
            return super().execute()

    class ConflictClient:
        def __init__(self):
            self.insert_attempts = 0
            self.versions = [1]

        def table(self, name):
            if name != "extracted_eligibility":
                raise AssertionError(name)
            query = ConflictQuery(self)
            if self.insert_attempts > 0:
                query.data = [{"version": 2}]
            return query

    client = ConflictClient()
    version = job_service._insert_extraction(
        client, uuid4(), {"job_title": "Engineer"}
    )
    assert version == 3
    assert client.insert_attempts == 2


def test_process_endpoint_is_owner_scoped(monkeypatch):
    app.dependency_overrides[get_current_user] = user
    job_id = uuid4()
    monkeypatch.setattr(job_service, "_get_job", lambda *_: None)
    try:
        response = TestClient(app).post(f"/api/v1/jobs/{job_id}/process")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_eligibility_is_owner_scoped(monkeypatch):
    app.dependency_overrides[get_current_user] = user
    job_id = uuid4()
    monkeypatch.setattr(job_service, "read_eligibility", lambda *_: None)
    try:
        response = TestClient(app).get(f"/api/v1/jobs/{job_id}/eligibility")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_process_endpoint_returns_completed_job(monkeypatch):
    app.dependency_overrides[get_current_user] = user
    job_id = uuid4()
    completed = {
        **job(job_id),
        "processing_status": "COMPLETED",
        "summary": analysis().summary.model_dump(mode="json"),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "original_filename": "notice.pdf",
        "file_size": 100,
        "mime_type": "application/pdf",
        "title": "Notice",
        "organization": "Board",
        "page_count": 1,
        "processing_error": None,
    }
    monkeypatch.setattr(job_service, "process_notification", lambda *_: completed)
    try:
        response = TestClient(app).post(f"/api/v1/jobs/{job_id}/process")
        assert response.status_code == 200
        assert response.json()["processing_status"] == "COMPLETED"
        assert response.json()["summary"]["organization"] == "Public Board"
    finally:
        app.dependency_overrides.clear()
