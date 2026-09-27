"""Minimal Supabase connectivity check for local development."""

from app.services.supabase_client import get_supabase_client


def main() -> None:
    client = get_supabase_client()
    table_probe = client.table("candidate_profiles").select("id").limit(1).execute()
    bucket_probe = client.storage.get_bucket("recruitment-pdfs")

    if bucket_probe.public:
        raise RuntimeError("recruitment-pdfs must be private, but Supabase reports it as public.")

    print(f"Database connection OK; candidate_profiles rows read: {len(table_probe.data)}")
    print(
        "Storage connection OK; "
        f"bucket={bucket_probe.name}, public={bucket_probe.public}"
    )


if __name__ == "__main__":
    main()
