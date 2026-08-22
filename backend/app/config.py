"""Application settings, read from environment variables or a .env file.

Never hardcode credentials. The .env file is gitignored; if the service role
key ever reaches the frontend or a commit, every user's data is exposed.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    renders_bucket: str = "renders"

    @property
    def configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
