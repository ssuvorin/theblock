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
    convex_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CONVEX_URL", "CRM_CONVEX_URL"),
    )
    convex_deploy_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CONVEX_DEPLOY_KEY", "CRM_CONVEX_DEPLOY_KEY"),
    )
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "CRM_OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1)
    embedding_version: str = "v1"
    embedding_batch_size: int = Field(default=64, ge=1, le=256)
    convex_upsert_batch_size: int = Field(default=50, ge=1, le=50)
    semantic_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ENCRYPTION_KEY", "CRM_ENCRYPTION_KEY"),
    )
    api_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    google_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "CRM_GOOGLE_CLIENT_ID"),
    )
    google_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "CRM_GOOGLE_CLIENT_SECRET"),
    )
    google_meeting_scheduling: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "GOOGLE_MEETING_SCHEDULING",
            "CRM_GOOGLE_MEETING_SCHEDULING",
        ),
    )
    meeting_default_minutes: int = Field(default=30, ge=5, le=480)
    connector_lookback_days: int = Field(default=90, ge=1, le=365)
    connector_page_limit: int = Field(default=10, ge=1, le=200)
    connector_batch_size: int = Field(default=100, ge=1, le=500)
    connector_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    collabute_mcp_url: str = Field(
        default="https://api.collabute.ai/api/mcp",
        validation_alias=AliasChoices("COLLABUTE_MCP_URL", "CRM_COLLABUTE_MCP_URL"),
    )
    collabute_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("COLLABUTE_CLIENT_ID", "CRM_COLLABUTE_CLIENT_ID"),
    )
    collabute_scopes: str = "meeting:read"
    oauth_state_minutes: int = Field(default=10, ge=1, le=60)


def _has_secret(key: SecretStr | None) -> bool:
    return bool(key and key.get_secret_value().strip())


def has_live_context_key(settings: Settings) -> bool:
    """An empty or blank CONTEXT_DEV_API_KEY must not count as a configured provider."""

    return _has_secret(settings.context_dev_api_key)


def has_secret_vault(settings: Settings) -> bool:
    """Connector tokens are only accepted when there is a key to encrypt them with."""

    return _has_secret(settings.encryption_key)


def has_google_oauth(settings: Settings) -> bool:
    """Google needs a confidential client, so both halves of the client must be present."""

    return bool(
        settings.google_client_id
        and settings.google_client_id.strip()
        and _has_secret(settings.google_client_secret)
        and has_secret_vault(settings)
    )


def has_collabute(settings: Settings) -> bool:
    """Collabute is a public PKCE client that registers itself, so only the vault is required."""

    return bool(settings.collabute_mcp_url.strip() and has_secret_vault(settings))


def has_semantic_index(settings: Settings) -> bool:
    """Semantic retrieval needs a Convex deployment and an embedding provider together."""

    return bool(
        settings.convex_url
        and settings.convex_url.strip()
        and _has_secret(settings.convex_deploy_key)
        and _has_secret(settings.openrouter_api_key)
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
