from typing import Any

from postgrest.exceptions import APIError

from app.dependencies.auth import AuthenticatedUser
from app.services.supabase_client import get_supabase_client


class ProfileAlreadyExistsError(Exception):
    """Raised when a user already has an active profile."""


def _profile_payload(user: AuthenticatedUser, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        **profile,
        "user_id": user.id,
    }


def get_profile(user: AuthenticatedUser) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("candidate_profiles")
        .select("*")
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_profile(
    user: AuthenticatedUser,
    profile: dict[str, Any],
) -> dict[str, Any]:
    if get_profile(user) is not None:
        raise ProfileAlreadyExistsError

    try:
        response = (
            get_supabase_client()
            .table("candidate_profiles")
            .insert(_profile_payload(user, profile))
            .execute()
        )
    except APIError as exc:
        if "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise ProfileAlreadyExistsError from exc
        raise
    return response.data[0]


def update_profile(
    user: AuthenticatedUser,
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    if get_profile(user) is None:
        return None

    response = (
        get_supabase_client()
        .table("candidate_profiles")
        .update(profile)
        .eq("user_id", user.id)
        .execute()
    )
    return response.data[0] if response.data else None


def delete_profile(user: AuthenticatedUser) -> bool:
    if get_profile(user) is None:
        return False

    get_supabase_client().table("candidate_profiles").delete().eq(
        "user_id", user.id
    ).execute()
    return True
