"""Supabase client.

Uses the service role key, which BYPASSES row level security. That is a
deliberate choice: FastAPI is the only thing talking to the database, and it
enforces ownership itself by filtering every query on user_id. RLS stays
enabled as a second layer in case anything ever connects with the anon key.

Because of that bypass, forgetting a user_id filter is a data leak, not a bug
caught by the database. Every query in app/db/ must include one.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    settings = get_settings()
    if not settings.configured:
        raise RuntimeError(
            "Supabase is not configured. Copy .env.example to .env and fill it in."
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)
