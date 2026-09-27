from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcessingStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    OCR_COMPLETED = "OCR_COMPLETED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobCreateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    organization: str | None = None


class JobResponse(BaseModel):
    id: UUID
    title: str | None
    organization: str | None
    original_filename: str
    file_size: int
    mime_type: str
    processing_status: ProcessingStatus
    page_count: int | None
    created_at: datetime
    updated_at: datetime
    processing_error: str | None
    summary: dict[str, Any] | None = None


class JobListResponse(BaseModel):
    id: UUID
    title: str | None
    organization: str | None
    original_filename: str
    processing_status: ProcessingStatus
    page_count: int | None
    created_at: datetime
    updated_at: datetime
    processing_error: str | None


class OCRResponse(BaseModel):
    job_id: UUID
    page_count: int
    pages: list[dict[str, Any]]


class EligibilityResponse(BaseModel):
    job_id: UUID
    version: int
    eligibility_json: dict[str, Any]
    extraction_status: str
    created_at: datetime
