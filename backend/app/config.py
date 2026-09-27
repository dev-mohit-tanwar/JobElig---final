from functools import lru_cache

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="JobEligAI API", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_prefix: str = Field(default="", alias="API_PREFIX")
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173"],
        alias="ALLOWED_ORIGINS",
    )
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_secret_key: SecretStr | None = Field(
        default=None,
        alias="SUPABASE_SECRET_KEY",
    )
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-3-flash-preview",
        alias="GEMINI_MODEL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
