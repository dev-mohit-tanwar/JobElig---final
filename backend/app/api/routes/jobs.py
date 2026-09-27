from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.schemas.job import EligibilityResponse, JobListResponse, JobResponse, OCRResponse
from app.services import job_service
from app.services import matching_service
from app.schemas.matching import EligibilityResultResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobListResponse])
def list_jobs(
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[JobListResponse]:
    try:
        return job_service.list_jobs(user)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to read notifications.") from exc


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def upload_job(
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    organization: str | None = Form(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
) -> JobResponse:
    if file is None:
        raise HTTPException(status_code=400, detail="A PDF file is required.")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    content = await file.read(job_service.MAX_FILE_SIZE + 1)
    if len(content) > job_service.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="PDF must be 15 MB or smaller.")
    try:
        return job_service.create_and_process(
            user, content, file.filename or "", title, organization
        )
    except job_service.DuplicateJobError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "job": JobResponse.model_validate(exc.job).model_dump(mode="json"),
            },
        )
    except job_service.JobServiceError as exc:
        detail = str(exc)
        code = 413 if "15 MB" in detail else 400 if "valid PDF" in detail else 500
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process notification.",
        ) from exc


@router.api_route(
    "/{job_id}",
    methods=["DELETE"],
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_job(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        job_service.delete_job(user, job_id)
    except job_service.JobServiceError as exc:
        code = 404 if str(exc) == "Notification not found." else 500
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JobResponse:
    try:
        job = job_service.read_job(user, job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to read notification.") from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return job


@router.get("/{job_id}/ocr", response_model=OCRResponse)
def get_ocr(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> OCRResponse:
    try:
        result = job_service.read_ocr(user, job_id)
    except job_service.JobServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return result


@router.post("/{job_id}/process", response_model=JobResponse)
def process_job(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JobResponse:
    try:
        return job_service.process_notification(user, job_id)
    except job_service.JobServiceError as exc:
        detail = str(exc)
        code = 404 if detail == "Notification not found." else 400 if "OCR text" in detail else 500
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to process notification.") from exc


@router.get("/{job_id}/eligibility", response_model=EligibilityResponse)
def get_eligibility(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> EligibilityResponse:
    try:
        result = job_service.read_eligibility(user, job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to read eligibility.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Eligibility not found.")
    return result


@router.post("/{job_id}/match", response_model=EligibilityResultResponse)
def match_job(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> EligibilityResultResponse:
    try:
        return matching_service.match_job(user, job_id)
    except matching_service.MatchingServiceError as exc:
        detail = str(exc)
        code = 404 if detail in {
            "Notification not found.",
            "Candidate profile not found.",
            "Eligibility extraction not found.",
        } else 500
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to match eligibility.") from exc


@router.get("/{job_id}/match", response_model=EligibilityResultResponse)
def get_match(
    job_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
) -> EligibilityResultResponse:
    try:
        result = matching_service.read_latest_result(user, job_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to read eligibility result.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Eligibility result not found.")
    return result
