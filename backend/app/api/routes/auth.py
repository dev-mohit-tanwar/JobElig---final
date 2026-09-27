from fastapi import APIRouter, Depends

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.schemas.profile import AuthenticatedIdentity

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthenticatedIdentity)
def read_current_identity(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(user_id=user.id, email=user.email)
