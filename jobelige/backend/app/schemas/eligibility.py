from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int | None = Field(default=None, ge=1)
    snippet: str | None = None


class PostEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_title: str | None = None
    vacancies: int | None = Field(default=None, ge=0)
    accepted_degrees: list[str] = Field(default_factory=list)
    accepted_branches: list[str] = Field(default_factory=list)
    minimum_percentage: float | None = Field(default=None, ge=0, le=100)
    minimum_cgpa: float | None = Field(default=None, ge=0, le=10)
    age_min: int | None = Field(default=None, ge=0)
    age_max: int | None = Field(default=None, ge=0)
    age_as_on_date: str | None = None
    age_relaxation: list[str] = Field(default_factory=list)
    category_requirements: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    nationality: str | None = None
    other_requirements: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class EligibilityExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_title: str | None = None
    organization: str | None = None
    posts: list[PostEligibility] = Field(default_factory=list)
    vacancies: int | None = Field(default=None, ge=0)
    accepted_degrees: list[str] = Field(default_factory=list)
    accepted_branches: list[str] = Field(default_factory=list)
    minimum_percentage: float | None = Field(default=None, ge=0, le=100)
    minimum_cgpa: float | None = Field(default=None, ge=0, le=10)
    age_min: int | None = Field(default=None, ge=0)
    age_max: int | None = Field(default=None, ge=0)
    age_as_on_date: str | None = None
    age_relaxation: list[str] = Field(default_factory=list)
    category_requirements: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    nationality: str | None = None
    other_requirements: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class RecruitmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: str | None = None
    recruitment_title: str | None = None
    vacancies: str | None = None
    qualifications: list[str] = Field(default_factory=list)
    age_requirements: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    category_requirements: list[str] = Field(default_factory=list)
    application_information: list[str] = Field(default_factory=list)
    unavailable_or_unclear: list[str] = Field(default_factory=list)
    factual_summary: str


class GeminiAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: RecruitmentSummary
    eligibility: EligibilityExtraction
