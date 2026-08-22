"""Verify the Supabase connection, schema, and storage bucket.

    python -m scripts.check_supabase
"""

from app.config import get_settings
from app.db.client import get_client

REQUIRED_TABLES = ("profiles", "notes", "renders")


def main() -> None:
    settings = get_settings()
    if not settings.configured:
        print("FAIL  .env is missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        return

    print(f"URL      {settings.supabase_url}")
    client = get_client()

    for table in REQUIRED_TABLES:
        try:
            client.table(table).select("*", count="exact").limit(0).execute()
            print(f"table    {table:<10} ok")
        except Exception as exc:
            print(f"table    {table:<10} FAIL  {type(exc).__name__}: {exc}")

    try:
        buckets = [b.name for b in client.storage.list_buckets()]
        mark = "ok" if settings.renders_bucket in buckets else "MISSING"
        print(f"bucket   {settings.renders_bucket:<10} {mark}   (found: {buckets})")
    except Exception as exc:
        print(f"bucket   FAIL  {type(exc).__name__}: {exc}")

    print(f"jwt      secret {'set' if settings.supabase_jwt_secret else 'MISSING'}")


if __name__ == "__main__":
    main()
