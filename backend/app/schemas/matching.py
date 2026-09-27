from enum import StrEnum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CriterionStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


class SemanticCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_name: str
    status: CriterionStatus
    candidate_value: str | None = None
    required_value: str | None = None
    explanation: str
    source_reference: str | None = None


class SemanticMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: list[SemanticCriterion]


class CriterionResultResponse(BaseModel):
    id: UUID
    eligibility_result_id: UUID
    criterion_name: str
    status: CriterionStatus
    candidate_value: str | None
    required_value: str | None
    explanation: str | None
    source_reference: str | None
    checking_method: str
    display_order: int


class EligibilityResultResponse(BaseModel):
    id: UUID
    user_id: UUID
    job_id: UUID
    candidate_profile_id: UUID
    overall_status: OverallStatus
    missing_information: list[str]
    warnings: list[str]
    final_explanation: str | None
    matching_json: dict[str, Any] | None
    created_at: datetime
    criterion_results: list[CriterionResultResponse] = []
