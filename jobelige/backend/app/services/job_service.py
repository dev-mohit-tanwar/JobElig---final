import json
import hashlib
import logging
import re
from typing import Any
from uuid import UUID, uuid4

from app.dependencies.auth import AuthenticatedUser
from app.schemas.eligibility import GeminiAnalysis
from app.services.gemini import (
    GeminiDocumentError,
    GeminiAnalysisError,
    GeminiConfigurationError,
    analyze_notification,
    extract_document,
)
from app.services.supabase_client import get_supabase_client

BUCKET = "recruitment-pdfs"
MAX_FILE_SIZE = 15 * 1024 * 1024
logger = logging.getLogger(__name__)


class JobServiceError(RuntimeError):
    """Safe, user-facing job processing error."""


class DuplicateJobError(JobServiceError):
    def __init__(self, job: dict[str, Any]):
        super().__init__("This PDF has already been uploaded.")
        self.job = job


def safe_filename(filename: str | None) -> str:
    raw_name = (filename or "recruitment-notification.pdf").replace("\\", "/").split("/")[-1]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._")
    if not stem:
        stem = "recruitment-notification"
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    return stem


def _get_job(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any] | None:
    response = (
        get_supabase_client()
        .table("job_notifications")
        .select("*")
        .eq("id", str(job_id))
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def _update(
    job_id: UUID,
    values: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any]:
    query = (
        get_supabase_client()
        .table("job_notifications")
        .update(values)
        .eq("id", str(job_id))
    )
    if user_id is not None:
        query = query.eq("user_id", user_id)
    response = (
        query.execute()
    )
    if not response.data:
        raise JobServiceError("Unable to update notification.")
    return response.data[0]


def create_and_process(
    user: AuthenticatedUser,
    pdf_bytes: bytes,
    original_filename: str,
    title: str | None,
    organization: str | None,
) -> dict[str, Any]:
    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise JobServiceError("PDF must be 15 MB or smaller.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise JobServiceError("The uploaded file is not a valid PDF.")

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    job_id = uuid4()
    filename = safe_filename(original_filename)
    storage_path = f"{user.id}/{job_id}/{filename}"
    client = get_supabase_client()
    record = {
        "id": str(job_id),
        "user_id": user.id,
        "title": title,
        "organization": organization,
        "original_filename": filename,
        "storage_path": storage_path,
        "file_size": len(pdf_bytes),
        "mime_type": "application/pdf",
        "processing_status": "UPLOADED",
        "file_hash": file_hash,
    }
    existing = (
        client.table("job_notifications")
        .select("*")
        .eq("user_id", user.id)
        .eq("file_hash", file_hash)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise DuplicateJobError(existing.data[0])
    try:
        client.table("job_notifications").insert(record).execute()
    except Exception as exc:
        existing = (
            client.table("job_notifications")
            .select("*")
            .eq("user_id", user.id)
            .eq("file_hash", file_hash)
            .limit(1)
            .execute()
        )
        if existing.data:
            raise DuplicateJobError(existing.data[0]) from exc
        raise JobServiceError("Unable to create notification.") from exc

    try:
        client.storage.from_(BUCKET).upload(
            storage_path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "false"},
        )
        _update(job_id, {"processing_status": "PROCESSING"}, user.id)
        pages = extract_document(pdf_bytes, filename)
        return _update(
            job_id,
            {
                "processing_status": "OCR_COMPLETED",
                "page_count": len(pages),
                "ocr_text": json.dumps(pages, ensure_ascii=False),
                "processing_error": None,
            },
            user.id,
        )
    except Exception as exc:
        try:
            _update(
                job_id,
                {"processing_status": "FAILED", "processing_error": _safe_error(exc)},
                user.id,
            )
        except Exception as status_exc:
            logger.error(
                "Unable to mark notification as FAILED: job_id=%s "
                "processing_error=%r status_update_error=%r",
                job_id,
                exc,
                status_exc,
            )
        raise JobServiceError(_safe_error(exc)) from exc


def _safe_error(error: Exception) -> str:
    if isinstance(error, GeminiConfigurationError):
        return "Gemini is not configured."
    if isinstance(error, GeminiDocumentError):
        return str(error)
    if isinstance(error, GeminiAnalysisError):
        return str(error)
    if isinstance(error, JobServiceError):
        return str(error)
    return "Notification processing failed."


def _is_version_conflict(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "23505" in message
        or "duplicate key" in message
        or "unique constraint" in message
        or "extracted_eligibility_job_id_version_key" in message
    )


def _insert_extraction(
    client: Any,
    job_id: UUID,
    eligibility_json: dict[str, Any],
) -> int:
    for _ in range(5):
        version_response = (
            client.table("extracted_eligibility")
            .select("version")
            .eq("job_id", str(job_id))
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        latest_version = (
            int(version_response.data[0]["version"])
            if version_response.data
            else 0
        )
        version = latest_version + 1
        try:
            client.table("extracted_eligibility").insert(
                {
                    "job_id": str(job_id),
                    "version": version,
                    "eligibility_json": eligibility_json,
                    "extraction_status": "COMPLETED",
                }
            ).execute()
            return version
        except Exception as exc:
            if not _is_version_conflict(exc):
                raise
    raise JobServiceError("Unable to allocate extraction version.")


def read_job(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any] | None:
    return _get_job(user, job_id)


def list_jobs(user: AuthenticatedUser) -> list[dict[str, Any]]:
    response = (
        get_supabase_client()
        .table("job_notifications")
        .select(
            "id,title,organization,original_filename,processing_status,"
            "page_count,created_at,updated_at,processing_error"
        )
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def delete_job(user: AuthenticatedUser, job_id: UUID) -> None:
    job = _get_job(user, job_id)
    if not job:
        raise JobServiceError("Notification not found.")
    client = get_supabase_client()
    try:
        storage_path = job.get("storage_path")
        if storage_path:
            client.storage.from_(BUCKET).remove([storage_path])
        response = (
            client.table("job_notifications")
            .delete()
            .eq("id", str(job_id))
            .eq("user_id", user.id)
            .execute()
        )
        if not response.data:
            raise JobServiceError("Unable to delete notification.")
    except JobServiceError:
        raise
    except Exception as exc:
        raise JobServiceError("Unable to delete notification.") from exc


def read_ocr(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any] | None:
    job = _get_job(user, job_id)
    if not job:
        return None
    try:
        pages = json.loads(job.get("ocr_text") or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise JobServiceError("Stored OCR content is invalid.") from exc
    return {"job_id": job_id, "page_count": job.get("page_count") or len(pages), "pages": pages}


def process_notification(
    user: AuthenticatedUser, job_id: UUID
) -> dict[str, Any]:
    job = _get_job(user, job_id)
    if not job:
        raise JobServiceError("Notification not found.")
    if not job.get("ocr_text"):
        raise JobServiceError("Notification has no OCR text.")

    _update(job_id, {"processing_status": "PROCESSING", "processing_error": None}, user.id)
    try:
        analysis = analyze_notification(job["ocr_text"])
        if not isinstance(analysis, GeminiAnalysis):
            analysis = GeminiAnalysis.model_validate(analysis)
        pages = json.loads(job["ocr_text"])
        page_numbers = {
            page["page"] for page in pages
            if isinstance(page, dict) and isinstance(page.get("page"), int)
        }
        references = list(analysis.eligibility.source_references)
        references.extend(
            reference
            for post in analysis.eligibility.posts
            for reference in post.source_references
        )
        if any(
            reference.page is not None and reference.page not in page_numbers
            for reference in references
        ):
            raise GeminiAnalysisError("Gemini returned invalid source references.")
        client = get_supabase_client()
        _insert_extraction(
            client,
            job_id,
            analysis.eligibility.model_dump(mode="json"),
        )
        return _update(
            job_id,
            {
                "summary": analysis.summary.model_dump(mode="json"),
                "processing_status": "COMPLETED",
                "processing_error": None,
            },
            user.id,
        )
    except Exception as exc:
        try:
            _update(
                job_id,
                {"processing_status": "FAILED", "processing_error": _safe_error(exc)},
                user.id,
            )
        except Exception:
            pass
        raise JobServiceError(_safe_error(exc)) from exc


def read_eligibility(
    user: AuthenticatedUser, job_id: UUID
) -> dict[str, Any] | None:
    if not _get_job(user, job_id):
        return None
    response = (
        get_supabase_client()
        .table("extracted_eligibility")
        .select("*")
        .eq("job_id", str(job_id))
        .eq("extraction_status", "COMPLETED")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
