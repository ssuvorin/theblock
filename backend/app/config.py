from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from process environment only."""

    model_config = SettingsConfigDict(
        env_prefix="CRM_",
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "Second Brain CRM"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./second_brain.db"
    auth_secret: SecretStr = Field(min_length=32)
    owner_password: SecretStr = Field(min_length=8)
    owner_email: str = "alex@example.test"
    owner_display_name: str = "Alex Ivanov"
    session_minutes: int = Field(default=480, ge=5, le=1440)
    cookie_secure: bool = True
    demo_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("DEMO_MODE", "CRM_DEMO_MODE"),
    )
    seed_demo_data: bool = True
    context_dev_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CONTEXT_DEV_API_KEY", "CRM_CONTEXT_DEV_API_KEY"),
    )
    context_dev_base_url: str = "https://api.context.dev/v1"
    context_timeout_seconds: float = Field(default=20.0, ge=1.0, le=60.0)


def has_live_context_key(settings: Settings) -> bool:
    """An empty or blank CONTEXT_DEV_API_KEY must not count as a configured provider."""

    key = settings.context_dev_api_key
    return bool(key and key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
