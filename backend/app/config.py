from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    learner_memory_store_path: Path = Field(
        default=Path("data/learner_memory.json"),
        validation_alias=AliasChoices("LEARNER_MEMORY_STORE_PATH", "learner_memory_store_path"),
    )
    session_ttl_seconds: int = Field(
        default=3600,
        ge=0,
        validation_alias=AliasChoices("SESSION_TTL_SECONDS", "PATENT_TUTOR_SESSION_TTL_SECONDS"),
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias=AliasChoices("PATENT_TUTOR_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    cors_allow_credentials: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "PATENT_TUTOR_CORS_ALLOW_CREDENTIALS",
            "CORS_ALLOW_CREDENTIALS",
        ),
    )
    environment: Literal["development", "test", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("PATENT_TUTOR_ENV", "APP_ENV"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped == "*":
                return ["*"]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


def load_service_settings() -> ServiceSettings:
    return ServiceSettings()
