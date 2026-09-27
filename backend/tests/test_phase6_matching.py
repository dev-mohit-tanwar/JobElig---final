import json
from datetime import date
from uuid import UUID, uuid4

from google.genai import errors as genai_errors
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.schemas.eligibility import EligibilityExtraction, PostEligibility
from app.schemas.matching import SemanticMatch
from app.services import matching_service
from app.services import gemini


USER_ID = "11111111-1111-1111-1111-111111111111"


def test_semantic_match_schema_constrains_exact_status_values():
    status_schema = (
        gemini.SEMANTIC_MATCH_RESPONSE_SCHEMA["properties"]["criteria"]["items"]
        ["properties"]["status"]
    )
    assert status_schema["enum"] == [
        "PASS",
        "FAIL",
        "NEEDS_VERIFICATION",
        "NOT_APPLICABLE",
    ]


def current_user():
    return AuthenticatedUser(id=USER_ID, email="user@example.com")


def extraction():
    return EligibilityExtraction(
        posts=[
            PostEligibility(
                post_title="Engineer",
                minimum_percentage=60,
                minimum_cgpa=7,
                age_max=30,
                experience_requirements=["2 years relevant experience"],
                accepted_degrees=["B.Tech"],
                accepted_branches=["Computer Science"],
                category_requirements=["OBC"],
                source_references=[{"page": 2, "snippet": "Engineer eligibility"}],
            )
        ]
    )


class Query:
    def __init__(self, data):
        self.data = data
        self.payload = None

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_):
        return self

    def insert(self, payload):
        self.payload = payload
        if isinstance(payload, list):
            self.data = [
                {
                    **row,
                    "id": str(uuid4()),
                    "eligibility_result_id": row.get("eligibility_result_id"),
                }
                for row in payload
            ]
        else:
            self.data = [{**payload, "id": str(uuid4()), "created_at": "2026-01-01T00:00:00Z"}]
        return self

    def execute(self):
        return type("Response", (), {"data": self.data})()


class Client:
    def __init__(self):
        self.result_query = Query([])
        self.criteria_query = Query([])

    def table(self, name):
        if name == "job_notifications":
            return Query([{"id": "job", "user_id": USER_ID}])
        if name == "candidate_profiles":
            return Query([])
        if name == "extracted_eligibility":
            return Query([{
                "version": 1,
                "eligibility_json": extraction().model_dump(mode="json"),
                "extraction_status": "COMPLETED",
            }])
        if name == "eligibility_results":
            self.result_query = Query([])
            return self.result_query
        if name == "criterion_results":
            self.criteria_query = Query([])
            return self.criteria_query
        raise AssertionError(name)


def profile(**overrides):
    value = {
        "id": str(uuid4()),
        "user_id": USER_ID,
        "date_of_birth": "2000-01-01",
        "percentage": 75,
        "cgpa": 8,
        "experience_years": 3,
        "degree": "B.Tech",
        "branch": "Computer Science",
        "category": "OBC",
        "nationality": "Indian",
        "certifications": [],
        "additional_information": {},
    }
    value.update(overrides)
    return value


def configure(monkeypatch, client=None, candidate=None):
    monkeypatch.setattr(matching_service, "get_supabase_client", lambda: client or Client())
    monkeypatch.setattr(matching_service, "get_profile", lambda _: candidate or profile())
    monkeypatch.setattr(
        matching_service,
        "analyze_semantic_match",
        lambda *_: SemanticMatch(criteria=[]),
    )


def test_unauthenticated_match_is_rejected():
    app.dependency_overrides.clear()
    response = TestClient(app).post(f"/api/v1/jobs/{uuid4()}/match")
    assert response.status_code == 401


def test_owner_scoping_and_missing_profile(monkeypatch):
    client = Client()
    monkeypatch.setattr(matching_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(matching_service, "get_profile", lambda _: None)
    try:
        matching_service.match_job(current_user(), uuid4())
    except matching_service.MatchingServiceError as exc:
        assert str(exc) == "Candidate profile not found."


def test_deterministic_age_percentage_cgpa_and_experience_inputs():
    criteria = matching_service._deterministic(extraction().posts[0], profile())
    criterion_names = {item["criterion_name"] for item in criteria}
    assert criterion_names >= {"age", "minimum_percentage", "minimum_cgpa", "experience"}
    assert next(item for item in criteria if item["criterion_name"] == "age")["status"] == "PASS"


def test_deterministic_failures_are_not_overridden_by_semantic_pass(monkeypatch):
    client = Client()
    configure(monkeypatch, client, profile(percentage=40))
    monkeypatch.setattr(
        matching_service,
        "analyze_semantic_match",
        lambda *_: SemanticMatch(criteria=[]),
    )
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "NOT_ELIGIBLE"
    assert any(item["status"] == "FAIL" for item in client.criteria_query.payload)


def test_missing_candidate_information_requires_verification(monkeypatch):
    client = Client()
    configure(monkeypatch, client, profile(date_of_birth=None, percentage=None, cgpa=None))
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "NEEDS_VERIFICATION"
    assert result["missing_information"]


def test_semantic_degree_branch_and_source_reference_are_persisted(monkeypatch):
    client = Client()
    configure(monkeypatch, client)
    monkeypatch.setattr(
        matching_service,
        "analyze_semantic_match",
        lambda *_: SemanticMatch(criteria=[
            {
                "criterion_name": "degree",
                "status": "PASS",
                "candidate_value": "B.Tech",
                "required_value": "B.Tech",
                "explanation": "Degree matches.",
                "source_reference": "Page 2, Engineer eligibility",
            },
            {
                "criterion_name": "branch",
                "status": "PASS",
                "candidate_value": "Computer Science",
                "required_value": "Computer Science",
                "explanation": "Branch matches.",
                "source_reference": "Page 99, fabricated",
            },
            {
                "criterion_name": "experience",
                "status": "PASS",
                "candidate_value": "3",
                "required_value": "2 years relevant experience",
                "explanation": "Experience matches.",
                "source_reference": "Page 2, Engineer eligibility",
            },
        ]),
    )
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "ELIGIBLE"
    # The degree criterion must have its real source reference preserved
    degree_item = next(
        item for item in client.criteria_query.payload
        if item["criterion_name"].endswith(":degree")
    )
    assert degree_item["source_reference"] == "Page 2, Engineer eligibility"
    # The branch criterion had a fabricated source reference — must be stripped
    assert all(
        item["source_reference"] != "Page 99, fabricated"
        for item in client.criteria_query.payload
    )


def test_missing_semantic_result_preserves_requested_criteria(monkeypatch):
    client = Client()
    configure(monkeypatch, client)
    monkeypatch.setattr(matching_service, "analyze_semantic_match", lambda *_: None)

    result = matching_service.match_job(current_user(), uuid4())

    assert result["overall_status"] == "NEEDS_VERIFICATION"
    names = {item["criterion_name"] for item in client.criteria_query.payload}
    assert names >= {"Engineer:degree", "Engineer:branch"}
    assert all(
        item["status"] == "NEEDS_VERIFICATION"
        for item in client.criteria_query.payload
        if item["criterion_name"].endswith((":degree", ":branch"))
    )




def test_match_result_returns_generated_criterion_ids(monkeypatch):
    client = Client()
    configure(monkeypatch, client)

    result = matching_service.match_job(current_user(), uuid4())

    assert result["criterion_results"]
    assert all(item.get("id") for item in result["criterion_results"])


def test_provider_failure_is_safe(monkeypatch):
    client = Client()
    configure(monkeypatch, client)
    monkeypatch.setattr(
        matching_service,
        "analyze_semantic_match",
        lambda *_: (_ for _ in ()).throw(
            matching_service.GeminiAnalysisError("Gemini analysis failed.")
        ),
    )
    try:
        matching_service.match_job(current_user(), uuid4())
    except matching_service.MatchingServiceError as exc:
        assert str(exc) == "Gemini analysis failed."


def test_semantic_match_diagnostic_is_sanitized_and_stage_aware(monkeypatch, caplog):
    secret = "phase6-gemini-secret"
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
            gemini.analyze_semantic_match({"degree": "B.Tech"}, {}, ["degree"])
        except gemini.GeminiAnalysisError as exc:
            assert str(exc) == "Gemini analysis failed."
        else:
            raise AssertionError("provider error should fail safely")

    diagnostic = caplog.text
    assert "Gemini semantic_match diagnostic:" in diagnostic
    assert "exception_type=ServerError" in diagnostic
    assert "http_status=500" in diagnostic
    assert "provider_status=INTERNAL" in diagnostic
    assert "provider_message=provider failure [REDACTED]" in diagnostic
    assert "model=gemini-3.5-flash" in diagnostic
    assert "stage=generate_content" in diagnostic
    assert secret not in diagnostic


def test_semantic_match_validation_diagnostic_identifies_pydantic_stage(monkeypatch, caplog):
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
            gemini.analyze_semantic_match({"degree": "B.Tech"}, {}, ["degree"])
        except gemini.GeminiAnalysisError as exc:
            assert str(exc) == "Gemini returned invalid structured output."
        else:
            raise AssertionError("invalid output should fail safely")

    assert "stage=pydantic_validation" in caplog.text


def test_rerun_creates_a_new_result(monkeypatch):
    first = Client()
    configure(monkeypatch, first)
    first_result = matching_service.match_job(current_user(), uuid4())
    second = Client()
    configure(monkeypatch, second)
    second_result = matching_service.match_job(current_user(), uuid4())
    assert first_result["id"] != second_result["id"]


def test_empty_eligibility_requires_verification_and_never_passes(monkeypatch):
    client = Client()
    empty = EligibilityExtraction()
    monkeypatch.setattr(matching_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(matching_service, "get_profile", lambda _: profile())
    client.table = lambda name: (
        Query([{"id": "job", "user_id": USER_ID}])
        if name == "job_notifications"
        else Query([{
            "version": 1,
            "eligibility_json": empty.model_dump(mode="json"),
            "extraction_status": "COMPLETED",
        }])
        if name == "extracted_eligibility"
        else client.result_query
        if name == "eligibility_results"
        else client.criteria_query
    )
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "NEEDS_VERIFICATION"
    assert not result["criterion_results"]
    assert any(
        "insufficient" in item.lower()
        for item in result["missing_information"]
    )
    assert any(
        "sufficient" in result["final_explanation"].lower()
        for _ in [None]
    )


def test_numeric_experience_creates_one_deterministic_criterion(monkeypatch):
    client = Client()
    configure(monkeypatch, client)
    result = matching_service.match_job(current_user(), uuid4())
    experience = [
        item for item in client.criteria_query.payload
        if item["criterion_name"].endswith(":experience")
    ]
    assert len(experience) == 1
    assert experience[0]["checking_method"] == "DETERMINISTIC"


def test_complex_experience_uses_semantic_check_once(monkeypatch):
    client = Client()
    candidate = profile(experience_years=3)
    configure(monkeypatch, client, candidate)
    original = extraction()
    original.posts[0].experience_requirements = ["experience in a related public-sector role"]
    monkeypatch.setattr(
        matching_service,
        "_latest_eligibility",
        lambda _: {
            "version": 1,
            "eligibility_json": original.model_dump(mode="json"),
        },
    )
    monkeypatch.setattr(
        matching_service,
        "analyze_semantic_match",
        lambda *_: SemanticMatch(criteria=[{
            "criterion_name": "experience",
            "status": "NEEDS_VERIFICATION",
            "candidate_value": "3",
            "required_value": "experience in a related public-sector role",
            "explanation": "Role equivalence requires verification.",
            "source_reference": "Page 2, Engineer eligibility",
        }]),
    )
    matching_service.match_job(current_user(), uuid4())
    experience = [
        item for item in client.criteria_query.payload
        if item["criterion_name"].endswith(":experience")
    ]
    assert len(experience) == 1
    assert experience[0]["checking_method"] == "GEMINI"


def test_numeric_experience_failure_wins_over_semantic_results(monkeypatch):
    client = Client()
    configure(monkeypatch, client, profile(experience_years=1))
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "NOT_ELIGIBLE"
    experience = [
        item for item in client.criteria_query.payload
        if item["criterion_name"].endswith(":experience")
    ]
    assert len(experience) == 1
    assert experience[0]["status"] == "FAIL"


def test_final_explanation_is_human_readable(monkeypatch):
    """final_explanation must not contain raw enum values or snake_case field names."""
    client = Client()
    configure(monkeypatch, client, profile(percentage=40))
    result = matching_service.match_job(current_user(), uuid4())
    assert result["overall_status"] == "NOT_ELIGIBLE"
    explanation = result["final_explanation"]
    # Must not contain raw enum or snake_case
    assert "NOT_ELIGIBLE" not in explanation
    assert "minimum_percentage" not in explanation
    assert "Failed:" not in explanation
    assert "Overall status:" not in explanation
    # Must contain a human-readable sentence
    assert "requirement" in explanation.lower()


def test_absent_percentage_and_cgpa_produce_no_criteria():
    """When minimum_percentage and minimum_cgpa are null, no criteria are created for them."""
    post = PostEligibility(
        post_title="Test Post",
        accepted_degrees=["B.Tech"],
        # minimum_percentage and minimum_cgpa deliberately absent (None)
    )
    criteria = matching_service._deterministic(post, profile())
    criterion_names = {item["criterion_name"] for item in criteria}
    assert "minimum_percentage" not in criterion_names
    assert "minimum_cgpa" not in criterion_names


def test_zero_percentage_and_cgpa_are_ignored_as_absent():
    """Gemini may return 0/0.0 for absent numeric fields before the nullable fix.
    The zero-guard must treat these as absent and not create criteria."""
    post = PostEligibility(
        post_title="Test Post",
        minimum_percentage=0,
        minimum_cgpa=0.0,
        accepted_degrees=["B.Tech"],
    )
    criteria = matching_service._deterministic(post, profile())
    criterion_names = {item["criterion_name"] for item in criteria}
    assert "minimum_percentage" not in criterion_names
    assert "minimum_cgpa" not in criterion_names


def test_absent_age_min_with_age_max_produces_correct_label():
    """When age_min is None and age_max is 32, required_value must be
    'Maximum 32 years' not '-32'."""
    post = PostEligibility(
        post_title="Test Post",
        age_max=32,
        # age_min is deliberately None
    )
    criteria = matching_service._deterministic(post, profile(date_of_birth="1998-01-01"))
    age_criterion = next(c for c in criteria if c["criterion_name"] == "age")
    required = age_criterion["required_value"]
    assert required is not None
    assert required.startswith("Maximum 32")
    assert "-32" not in required
    assert "None" not in required


def test_dob_missing_produces_needs_verification_with_helpful_message():
    """When DOB is absent, the age criterion must be NEEDS_VERIFICATION with
    a user-friendly explanation (not 'missing or invalid')."""
    post = PostEligibility(post_title="Test Post", age_max=32)
    criteria = matching_service._deterministic(post, profile(date_of_birth=None))
    age_criterion = next(c for c in criteria if c["criterion_name"] == "age")
    assert age_criterion["status"] == "NEEDS_VERIFICATION"
    explanation = age_criterion["explanation"]
    assert "date of birth" in explanation.lower() or "dob" in explanation.lower()
    assert "required" in explanation.lower() or "missing" in explanation.lower()


def test_criterion_names_use_post_title_colon_field_format(monkeypatch):
    """Stored criterion_name must follow 'PostTitle:field_name' format.
    The frontend splits on the last colon to extract the display name."""
    client = Client()
    configure(monkeypatch, client)
    matching_service.match_job(current_user(), uuid4())
    for item in client.criteria_query.payload:
        name = item["criterion_name"]
        assert ":" in name, (
            f"criterion_name '{name}' must contain a colon separating post title from field"
        )
        # The part after the last colon must be a recognizable field name
        field_part = name.rsplit(":", 1)[1]
        assert field_part and " " not in field_part, (
            f"Field part '{field_part}' should be a snake_case field name"
        )
