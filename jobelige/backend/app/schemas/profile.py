from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    date_of_birth: date | None = None
    category: str | None = None
    degree: str | None = None
    branch: str | None = None
    percentage: Decimal | None = Field(default=None, ge=0, le=100)
    cgpa: Decimal | None = Field(default=None, ge=0, le=10)
    graduation_year: int | None = Field(default=None, ge=1900, le=2200)
    experience_years: Decimal | None = Field(default=None, ge=0)
    certifications: list[str] = Field(default_factory=list)
    nationality: str | None = None
    additional_information: dict[str, Any] = Field(default_factory=dict)


class CandidateProfileResponse(CandidateProfileInput):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class AuthenticatedIdentity(BaseModel):
    user_id: UUID
    email: str | None = None
