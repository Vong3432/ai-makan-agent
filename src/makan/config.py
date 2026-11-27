"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    public_base_url: str = "http://localhost:8000"

    # Auth: "dev" = fixed test user, no OAuth. "supabase" = OAuth 2.1 via Supabase Auth (P2).
    auth_mode: Literal["dev", "supabase"] = "dev"
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"

    # Supabase
    supabase_url: str = "http://host.docker.internal:54321"
    supabase_anon_key: SecretStr = SecretStr("")
    supabase_service_role_key: SecretStr = SecretStr("")

    # Google Places
    google_api_key: SecretStr = SecretStr("")
    # Biases Places results toward this country (CLDR code); empty = no bias.
    places_region_code: str = "MY"

    # LLM
    anthropic_api_key: SecretStr = SecretStr("")
    llm_model: str = "claude-haiku-5-5"

    # Rate limiting (off for testing — enable before public launch)
    rate_limit_enabled: bool = False
    rate_limit_per_day: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
