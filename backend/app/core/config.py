from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/inbox_assistant"
    encryption_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/redirect"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    session_secret: str = ""
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    bounce_webhook_secret: str = ""
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_free: str = "price_free"
    stripe_price_pro: str = "price_pro"
    stripe_price_team: str = "price_team"

    # Integrations (optional)
    hubspot_api_key: str = ""
    lead_intel_api_url: str = ""
    lead_intel_api_key: str = ""

    # Microsoft Graph / Outlook (Phase 4)
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = "http://localhost:8000/auth/microsoft/redirect"

    # Public API (Phase 5)
    public_api_keys: str = ""

    # Background jobs
    scheduler_enabled: bool = False
    sync_interval_minutes: int = 15
    digest_hour_utc: int = 11
    scheduler_tick_seconds: int = 60
    auto_process_limit: int = 25
    auto_process_max_results: int = 20


settings = Settings()


def validate_config() -> list[str]:
    """Return configuration problems; raise when they affect production."""
    problems: list[str] = []
    if not settings.encryption_key:
        problems.append(
            "ENCRYPTION_KEY is not set (OAuth tokens will not be encrypted at rest)"
        )
    if not settings.session_secret:
        problems.append(
            "SESSION_SECRET is not set (sessions and OAuth state are insecure)"
        )
    production = settings.frontend_url.startswith("https://")
    if production and problems:
        raise RuntimeError(
            "Invalid production configuration: " + "; ".join(problems)
        )
    return problems