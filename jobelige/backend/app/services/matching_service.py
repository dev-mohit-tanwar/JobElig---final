import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.dependencies.auth import AuthenticatedUser
from app.schemas.eligibility import EligibilityExtraction, PostEligibility
from app.schemas.matching import CriterionStatus, OverallStatus
from app.services.gemini import (
    GeminiAnalysisError,
    GeminiConfigurationError,
    analyze_semantic_match,
)
from app.services.profile_service import get_profile
from app.services.supabase_client import get_supabase_client


class MatchingServiceError(RuntimeError):
    """Safe matching error."""


def _job(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any] | None:
    response = (
        get_supabase_client().table("job_notifications").select("id,user_id").eq(
            "id", str(job_id)
        ).eq("user_id", user.id).limit(1).execute()
    )
    return response.data[0] if response.data else None


def _latest_eligibility(job_id: UUID) -> dict[str, Any] | None:
    response = (
        get_supabase_client().table("extracted_eligibility").select("*")
        .eq("job_id", str(job_id)).eq("extraction_status", "COMPLETED")
        .order("version", desc=True).limit(1).execute()
    )
    return response.data[0] if response.data else None


def _criterion(
    name: str, status: CriterionStatus, candidate: Any, required: Any,
    explanation: str, source: Any = None, method: str = "DETERMINISTIC",
) -> dict[str, Any]:
    return {
        "criterion_name": name,
        "status": status.value,
        "candidate_value": None if candidate is None else str(candidate),
        "required_value": None if required is None else str(required),
        "explanation": explanation,
        "source_reference": _source_text(source),
        "checking_method": method,
    }


def _source_text(source: Any) -> str | None:
    if not source:
        return None
    if isinstance(source, str):
        return source
    page = source.get("page") if isinstance(source, dict) else getattr(source, "page", None)
    snippet = source.get("snippet") if isinstance(source, dict) else getattr(source, "snippet", None)
    parts = []
    if page is not None:
        parts.append(f"Page {page}")
    if snippet:
        parts.append(snippet)
    return ", ".join(parts) or None


def _age_on(dob: Any, as_on: Any) -> int | None:
    if not dob:
        return None
    try:
        birth = date.fromisoformat(str(dob))
        reference = _parse_date(as_on) if as_on else date.today()
    except (TypeError, ValueError):
        return None
    return reference.year - birth.year - ((reference.month, reference.day) < (birth.month, birth.day))


def _parse_date(value: Any) -> date:
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%d %B %Y").date()


def _numeric_experience_minimum(requirements: list[str]) -> Decimal | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        " ".join(requirements),
        re.I,
    )
    return Decimal(match.group(1)) if match else None


def _age_required_label(age_min: int | None, age_max: int | None, age_as_on_date: str | None) -> str:
    """Produce a human-readable required age string, e.g. 'Maximum 32 years'."""
    age_min = age_min or None
    cutoff = ""
    if age_as_on_date:
        try:
            d = _parse_date(age_as_on_date)
            cutoff = f" as on {d.strftime('%d %B %Y')}"
        except (TypeError, ValueError):
            cutoff = f" as on {age_as_on_date}"
    if age_min is not None and age_max is not None:
        return f"Between {age_min} and {age_max} years{cutoff}"
    if age_max is not None:
        return f"Maximum {age_max} years{cutoff}"
    if age_min is not None:
        return f"Minimum {age_min} years{cutoff}"
    return "Not specified"


def _candidate_age_label(dob: Any, age: int | None) -> str:
    """Produce a human-readable candidate age string."""
    if dob and age is not None:
        try:
            birth = date.fromisoformat(str(dob))
            dob_str = birth.strftime("%d %B %Y")
            return f"Date of birth: {dob_str} (Age: {age} years)"
        except ValueError:
            pass
    if age is not None:
        return f"{age} years"
    return None


def _deterministic(post: PostEligibility, profile: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    # age_source and numeric_source are intentionally None:
    # We do not attach the qualification-page snippet to age, percentage, or CGPA rows.
    age_source = None
    numeric_source = None
    if post.age_min is not None or post.age_max is not None:
        dob = profile.get("date_of_birth")
        age = _age_on(dob, post.age_as_on_date)
        age_min = post.age_min or None
        if age is None:
            status = CriterionStatus.NEEDS_VERIFICATION
            explanation = "Date of birth is required to verify the age requirement."
        elif (
            age_min is not None and age < age_min
        ) or (
            post.age_max is not None and age > post.age_max
        ):
            status = CriterionStatus.FAIL
            explanation = "Candidate age is outside the stated age range."
        else:
            status = CriterionStatus.PASS
            explanation = "Candidate age satisfies the stated age range."
        candidate_age_str = _candidate_age_label(dob, age)
        required_age_str = _age_required_label(age_min, post.age_max, post.age_as_on_date)
        results.append(_criterion("age", status, candidate_age_str, required_age_str, explanation, age_source))
    for name, value, minimum in (
        ("minimum_percentage", profile.get("percentage"), post.minimum_percentage),
        ("minimum_cgpa", profile.get("cgpa"), post.minimum_cgpa),
    ):
        # Skip if the notification did not specify a minimum. Guard against Gemini
        # returning 0 or 0.0 for an absent field (schema coercion before nullable fix).
        if minimum is None or minimum == 0:
            continue
        status = CriterionStatus.NEEDS_VERIFICATION if value is None else (
            CriterionStatus.PASS if Decimal(str(value)) >= Decimal(str(minimum)) else CriterionStatus.FAIL
        )
        results.append(_criterion(name, status, value, minimum,
            "Candidate value meets the minimum." if status == CriterionStatus.PASS else
            "Candidate value is below the minimum." if status == CriterionStatus.FAIL else
            "Candidate value is missing.", numeric_source))
    if post.experience_requirements:
        minimum = _numeric_experience_minimum(post.experience_requirements)
        if minimum is not None:
            value = profile.get("experience_years")
            status = CriterionStatus.NEEDS_VERIFICATION if value is None else (
                CriterionStatus.PASS if Decimal(str(value)) >= minimum else CriterionStatus.FAIL
            )
            results.append(_criterion(
                "experience", status, value, minimum,
                "Candidate experience meets the explicit minimum." if status == CriterionStatus.PASS
                else "Candidate experience is below the explicit minimum." if status == CriterionStatus.FAIL
                else "Candidate experience is missing.", numeric_source,
            ))
    if post.nationality:
        value = profile.get("nationality")
        status = CriterionStatus.NEEDS_VERIFICATION if not value else (
            CriterionStatus.PASS if value.casefold() == post.nationality.casefold() else CriterionStatus.FAIL
        )
        results.append(_criterion("nationality", status, value, post.nationality,
            "Nationality matches the explicit requirement." if status == CriterionStatus.PASS else
            "Nationality does not match the explicit requirement." if status == CriterionStatus.FAIL else
            "Candidate nationality is missing.", numeric_source))
    if post.category_requirements:
        value = profile.get("category")
        required = "; ".join(post.category_requirements)
        status = CriterionStatus.NEEDS_VERIFICATION if not value else (
            CriterionStatus.PASS if any(value.casefold() in item.casefold() for item in post.category_requirements)
            else CriterionStatus.FAIL
        )
        results.append(_criterion("category", status, value, required,
            "Candidate category matches an explicit requirement." if status == CriterionStatus.PASS else
            "Candidate category does not match the explicit requirement." if status == CriterionStatus.FAIL else
            "Candidate category is missing.", numeric_source))
    return results


def _safe_error(error: Exception) -> str:
    if isinstance(error, GeminiConfigurationError):
        return "Gemini is not configured."
    if isinstance(error, GeminiAnalysisError):
        return str(error)
    if isinstance(error, MatchingServiceError):
        return str(error)
    return "Eligibility matching failed."


def match_job(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any]:
    if not _job(user, job_id):
        raise MatchingServiceError("Notification not found.")
    profile = get_profile(user)
    if not profile:
        raise MatchingServiceError("Candidate profile not found.")
    extraction = _latest_eligibility(job_id)
    if not extraction:
        raise MatchingServiceError("Eligibility extraction not found.")
    try:
        eligibility = EligibilityExtraction.model_validate(extraction["eligibility_json"])
        posts = eligibility.posts or [PostEligibility(
            post_title=eligibility.job_title,
            vacancies=eligibility.vacancies,
            accepted_degrees=eligibility.accepted_degrees,
            accepted_branches=eligibility.accepted_branches,
            minimum_percentage=eligibility.minimum_percentage,
            minimum_cgpa=eligibility.minimum_cgpa,
            age_min=eligibility.age_min, age_max=eligibility.age_max,
            age_as_on_date=eligibility.age_as_on_date,
            age_relaxation=eligibility.age_relaxation,
            category_requirements=eligibility.category_requirements,
            experience_requirements=eligibility.experience_requirements,
            certifications=eligibility.certifications,
            nationality=eligibility.nationality,
            other_requirements=eligibility.other_requirements,
            exceptions=eligibility.exceptions,
            uncertainty=eligibility.uncertainty,
            source_references=eligibility.source_references,
        )]
        all_results = []
        post_outcomes = []
        if eligibility.uncertainty:
            all_results.append(_criterion(
                "notification_uncertainty",
                CriterionStatus.NEEDS_VERIFICATION,
                None,
                "; ".join(eligibility.uncertainty),
                "The recruitment notification contains ambiguous or conflicting requirements.",
                eligibility.source_references[0].model_dump(mode="json")
                if eligibility.source_references else None,
                "DETERMINISTIC",
            ))
        for index, post in enumerate(posts):
            deterministic = _deterministic(post, profile)

            if post.uncertainty:
                deterministic.append(_criterion(
                    "notification_uncertainty",
                    CriterionStatus.NEEDS_VERIFICATION,
                    None,
                    "; ".join(post.uncertainty),
                    "The recruitment notification contains ambiguous or conflicting requirements.",
                    post.source_references[0].model_dump(mode="json")
                    if post.source_references else None,
                    "DETERMINISTIC",
                ))
            semantic_names = []
            if post.accepted_degrees:
                semantic_names.append("degree")
            if post.accepted_branches:
                semantic_names.append("branch")
            if post.certifications:
                semantic_names.append("certifications")
            if post.other_requirements:
                semantic_names.append("other_requirements")
            if post.experience_requirements and _numeric_experience_minimum(
                post.experience_requirements
            ) is None:
                semantic_names.append("experience")
            semantic = analyze_semantic_match(
                post.model_dump(mode="json"),
                {key: profile.get(key) for key in ("degree", "branch", "certifications", "additional_information")},
                semantic_names,
            ) if semantic_names else None
            semantic_results = []
            if semantic is not None:
                requested = set(semantic_names)
                returned = set()
                allowed_sources = {
                    _source_text(reference)
                    for reference in post.source_references
                }
                for item in semantic.criteria:
                    data = item.model_dump(mode="json")
                    data["checking_method"] = "GEMINI"
                    returned.add(item.criterion_name)
                    if data["source_reference"] not in allowed_sources:
                        data["source_reference"] = None
                    semantic_results.append(data)
                for criterion_name in requested - returned:
                    semantic_results.append({
                        "criterion_name": criterion_name,
                        "status": CriterionStatus.NEEDS_VERIFICATION.value,
                        "candidate_value": None,
                        "required_value": None,
                        "explanation": "Gemini did not return a result for this criterion.",
                        "source_reference": None,
                        "checking_method": "GEMINI",
                    })
            elif semantic_names:
                semantic_results = [
                    {
                        "criterion_name": criterion_name,
                        "status": CriterionStatus.NEEDS_VERIFICATION.value,
                        "candidate_value": None,
                        "required_value": None,
                        "explanation": "This criterion could not be evaluated automatically.",
                        "source_reference": None,
                        "checking_method": "GEMINI",
                    }
                    for criterion_name in semantic_names
                ]
            combined = deterministic + semantic_results
            for result in combined:
                # Encode post title into criterion_name as "PostTitle:field_name".
                # The frontend splits on the last colon to get the display name.
                result["criterion_name"] = f"{post.post_title or 'post'}:{result['criterion_name']}"
                result["display_order"] = len(all_results)
                all_results.append(result)
            post_outcomes.append(all(item["status"] == CriterionStatus.PASS.value for item in combined))
        failed = any(item["status"] == CriterionStatus.FAIL.value for item in all_results)
        needs = any(item["status"] == CriterionStatus.NEEDS_VERIFICATION.value for item in all_results)
        # missing_information: resolve the human-readable criterion part from
        # the "PostTitle:field_name" encoded criterion_name.
        def _human_criterion_label(raw_name: str) -> str:
            """Return the human-readable label for a 'PostTitle:field_name' criterion name."""
            LABEL_MAP = {
                "age": "Age",
                "minimum_percentage": "Minimum Percentage",
                "minimum_cgpa": "Minimum CGPA",
                "experience": "Experience",
                "nationality": "Nationality",
                "category": "Category",
                "degree": "Educational Qualification",
                "branch": "Branch",
                "certifications": "Certifications",
                "other_requirements": "Other Requirements",
                "notification_uncertainty": "Notification requirements need review",
            }
            colon_idx = raw_name.rfind(":")
            field = raw_name[colon_idx + 1:].strip() if colon_idx != -1 else raw_name
            return LABEL_MAP.get(field, field.replace("_", " ").title())


        missing = [
            _human_criterion_label(item["criterion_name"])
            for item in all_results
            if item["status"] == CriterionStatus.NEEDS_VERIFICATION.value
        ]
        if not all_results:
            missing.append("Insufficient actionable eligibility information")
        overall = OverallStatus.NOT_ELIGIBLE if failed else (
            OverallStatus.ELIGIBLE
            if all_results and any(post_outcomes) and not needs
            else OverallStatus.NEEDS_VERIFICATION
        )
        warnings = list(eligibility.uncertainty)
        # Build a human-readable final_explanation (no raw enum values or snake_case)
        n_pass = sum(1 for item in all_results if item["status"] == CriterionStatus.PASS.value)
        n_fail = sum(1 for item in all_results if item["status"] == CriterionStatus.FAIL.value)
        n_verify = sum(1 for item in all_results if item["status"] == CriterionStatus.NEEDS_VERIFICATION.value)
        if overall == OverallStatus.ELIGIBLE:
            explanation_parts = ["Your profile satisfies all checked eligibility requirements."]
        elif overall == OverallStatus.NOT_ELIGIBLE:
            explanation_parts = ["Your profile does not meet one or more eligibility requirements."]
            if n_fail == 1:
                explanation_parts.append("1 requirement was not met.")
            elif n_fail > 1:
                explanation_parts.append(f"{n_fail} requirements were not met.")
        else:
            explanation_parts = [
                "Some requirements could not be verified automatically and may need manual review."
            ]
        if n_pass > 0:
            explanation_parts.append(
                f"{n_pass} requirement{'s' if n_pass != 1 else ''} "
                f"{'were' if n_pass != 1 else 'was'} satisfied."
            )
        if n_verify > 0:
            explanation_parts.append(
                f"{n_verify} requirement{'s' if n_verify != 1 else ''} "
                f"require{'s' if n_verify == 1 else ''} verification."
            )

        if not all_results:
            explanation_parts.append(
                "The notification does not contain sufficient actionable eligibility information."
            )
        client = get_supabase_client()
        result_response = client.table("eligibility_results").insert({
            "user_id": user.id, "job_id": str(job_id), "candidate_profile_id": profile["id"],
            "overall_status": overall.value, "missing_information": missing,
            "warnings": warnings, "final_explanation": " ".join(explanation_parts),
            "matching_json": {
                "eligibility_version": extraction["version"],
                "posts": post_outcomes,
                "criteria": all_results,
            },
        }).execute()
        result = result_response.data[0]
        rows = [{**item, "eligibility_result_id": result["id"]} for item in all_results]
        if rows:
            criterion_response = client.table("criterion_results").insert(rows).execute()
            rows = criterion_response.data or []
        result["criterion_results"] = rows
        return result
    except Exception as exc:
        raise MatchingServiceError(_safe_error(exc)) from exc


def read_latest_result(user: AuthenticatedUser, job_id: UUID) -> dict[str, Any] | None:
    if not _job(user, job_id):
        return None
    response = get_supabase_client().table("eligibility_results").select("*").eq(
        "job_id", str(job_id)
    ).eq("user_id", user.id).order("created_at", desc=True).limit(1).execute()
    if not response.data:
        return None
    result = response.data[0]
    criteria = get_supabase_client().table("criterion_results").select("*").eq(
        "eligibility_result_id", result["id"]
    ).order("display_order").execute()
    result["criterion_results"] = criteria.data or []
    return result
