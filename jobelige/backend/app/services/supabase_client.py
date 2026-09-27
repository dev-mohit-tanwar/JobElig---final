from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client:
    """Create the server-only Supabase client from environment configuration."""
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY must be configured "
            "before using Supabase."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key.get_secret_value(),
    )
