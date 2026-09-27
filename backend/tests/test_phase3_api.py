from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.services import profile_service


USER_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_USER_ID = UUID("22222222-2222-2222-2222-222222222222")


def profile_for(user_id: UUID) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "full_name": "Test Candidate",
        "date_of_birth": date(2000, 1, 1).isoformat(),
        "category": "General",
        "degree": "B.Tech",
        "branch": "Computer Science",
        "percentage": "80",
        "cgpa": "8.2",
        "graduation_year": 2022,
        "experience_years": "1.5",
        "certifications": ["AWS"],
        "nationality": "Indian",
        "additional_information": {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


@pytest.fixture
def client(monkeypatch):
    profiles = {}

    def current_user():
        return AuthenticatedUser(id=str(USER_ID), email="user@example.com")

    def get_profile(user):
        return profiles.get(user.id)

    def create_profile(user, payload):
        if user.id in profiles:
            raise profile_service.ProfileAlreadyExistsError
        record = profile_for(UUID(user.id))
        record.update(payload)
        profiles[user.id] = record
        return record

    def update_profile(user, payload):
        record = profiles.get(user.id)
        if record is None:
            return None
        record.update(payload)
        return record

    def delete_profile(user):
        return profiles.pop(user.id, None) is not None

    monkeypatch.setattr(profile_service, "get_profile", get_profile)
    monkeypatch.setattr(profile_service, "create_profile", create_profile)
    monkeypatch.setattr(profile_service, "update_profile", update_profile)
    monkeypatch.setattr(profile_service, "delete_profile", delete_profile)
    app.dependency_overrides[get_current_user] = current_user
    yield TestClient(app), profiles, current_user
    app.dependency_overrides.clear()


def test_health_works(client):
    response = client[0].get("/health")
    assert response.status_code == 200


def test_profile_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v1/profile")
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_invalid_bearer_token_returns_401(monkeypatch):
    class InvalidAuth:
        def get_user(self, token):
            raise ValueError("invalid token")

    class FakeClient:
        auth = InvalidAuth()

    from app.dependencies import auth

    monkeypatch.setattr(auth, "get_supabase_client", lambda: FakeClient())
    response = TestClient(app).get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer malformed-token"},
    )
    assert response.status_code == 401


def test_authenticated_user_can_create_and_read_own_profile(client):
    http, _, _ = client
    payload = {"full_name": "Test Candidate", "percentage": 80, "cgpa": 8.2}
    created = http.post("/api/v1/profile", json=payload)
    assert created.status_code == 201
    assert created.json()["user_id"] == str(USER_ID)
    assert http.get("/api/v1/profile").status_code == 200


def test_duplicate_profile_is_rejected(client):
    http, _, _ = client
    payload = {"full_name": "Test Candidate"}
    assert http.post("/api/v1/profile", json=payload).status_code == 201
    assert http.post("/api/v1/profile", json=payload).status_code == 409


def test_client_cannot_supply_user_id(client):
    response = client[0].post(
        "/api/v1/profile",
        json={"user_id": str(OTHER_USER_ID), "full_name": "Other User"},
    )
    assert response.status_code == 422


def test_update_only_affects_authenticated_user(client):
    http, profiles, current_user = client
    profiles[str(OTHER_USER_ID)] = profile_for(OTHER_USER_ID)
    profiles[str(USER_ID)] = profile_for(USER_ID)
    response = http.put("/api/v1/profile", json={"full_name": "Updated"})
    assert response.status_code == 200
    assert profiles[str(USER_ID)]["full_name"] == "Updated"
    assert profiles[str(OTHER_USER_ID)]["full_name"] == "Test Candidate"


def test_read_does_not_expose_another_users_profile(client):
    http, profiles, _ = client
    profiles[str(OTHER_USER_ID)] = profile_for(OTHER_USER_ID)
    response = http.get("/api/v1/profile")
    assert response.status_code == 404


def test_delete_only_affects_authenticated_user(client):
    http, profiles, _ = client
    profiles[str(OTHER_USER_ID)] = profile_for(OTHER_USER_ID)
    profiles[str(USER_ID)] = profile_for(USER_ID)
    response = http.delete("/api/v1/profile")
    assert response.status_code == 204
    assert str(OTHER_USER_ID) in profiles
    assert str(USER_ID) not in profiles
