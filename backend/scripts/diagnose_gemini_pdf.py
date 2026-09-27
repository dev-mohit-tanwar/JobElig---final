import json
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


MODEL = "gemini-3.5-flash"
PDF_NAME = "JobEligAI_SSC_JE_2025_Test_Notification.pdf"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
PDF_CANDIDATES = (
    PROJECT_ROOT.parent / PDF_NAME,
    PROJECT_ROOT / ".kilo" / PDF_NAME,
    PROJECT_ROOT / PDF_NAME,
    BACKEND_ROOT / PDF_NAME,
)


def load_env_value(name: str) -> str | None:
    env_path = BACKEND_ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return os.environ.get(name)


def provider_details(error: Exception) -> tuple[Any, Any, Any]:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    provider_status = None
    provider_message = str(error)
    for argument in getattr(error, "args", ()):
        if not isinstance(argument, dict):
            continue
        payload = argument.get("error", argument)
        if isinstance(payload, dict):
            status = status or payload.get("code")
            provider_status = payload.get("status")
            provider_message = payload.get("message") or provider_message
    return status, provider_status, provider_message


def main() -> None:
    pdf_path = next((path for path in PDF_CANDIDATES if path.is_file()), None)
    if pdf_path is None:
        raise FileNotFoundError(
            f"Could not find {PDF_NAME} in: "
            + ", ".join(str(path) for path in PDF_CANDIDATES)
        )

    api_key = load_env_value("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured in backend/.env")

    pdf_bytes = pdf_path.read_bytes()
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            "Read this PDF and return its title and organization.",
        ],
    )
    print(response.text or json.dumps(getattr(response, "parsed", None), default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        status, provider_status, provider_message = provider_details(error)
        print(f"exception_type={type(error).__name__}")
        print(f"http_status={status}")
        print(f"provider_status={provider_status}")
        print(f"provider_message={provider_message}")
        print(f"model={MODEL}")
        raise
