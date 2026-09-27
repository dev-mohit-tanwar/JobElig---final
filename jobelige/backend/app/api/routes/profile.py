from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.schemas.profile import CandidateProfileInput, CandidateProfileResponse
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=CandidateProfileResponse)
def read_profile(
    user: AuthenticatedUser = Depends(get_current_user),
) -> CandidateProfileResponse:
    try:
        profile = profile_service.get_profile(user)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to read profile.",
        ) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


@router.post(
    "",
    response_model=CandidateProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    payload: CandidateProfileInput,
    user: AuthenticatedUser = Depends(get_current_user),
) -> CandidateProfileResponse:
    try:
        return profile_service.create_profile(user, payload.model_dump(mode="json"))
    except profile_service.ProfileAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active profile already exists.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create profile.",
        ) from exc


@router.put("", response_model=CandidateProfileResponse)
def update_profile(
    payload: CandidateProfileInput,
    user: AuthenticatedUser = Depends(get_current_user),
) -> CandidateProfileResponse:
    try:
        profile = profile_service.update_profile(user, payload.model_dump(mode="json"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update profile.",
        ) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    try:
        deleted = profile_service.delete_profile(user)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete profile.",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
