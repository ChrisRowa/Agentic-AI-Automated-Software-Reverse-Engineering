"""
Core configuration management for Reverse Engineering AI Platform.
Reads from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Reverse Engineering AI Platform"
    app_version: str = "1.0.0"
    app_env: str = Field(default="development", alias="APP_ENV", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL", validation_alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG", validation_alias="DEBUG")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://reverse_user:reverse_pass@localhost:5432/reverse_engineering_db",
        alias="DATABASE_URL", validation_alias="DATABASE_URL",
    )
    sync_database_url: str = Field(
        default="postgresql://reverse_user:reverse_pass@localhost:5432/reverse_engineering_db",
        alias="SYNC_DATABASE_URL", validation_alias="SYNC_DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL", validation_alias="REDIS_URL")

    # LLM
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY", validation_alias="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY", validation_alias="GOOGLE_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY", validation_alias="ANTHROPIC_API_KEY")

    primary_llm_provider: str = Field(default="openai", alias="PRIMARY_LLM_PROVIDER", validation_alias="PRIMARY_LLM_PROVIDER")
    primary_llm_model: str = Field(default="gpt-4o-mini", alias="PRIMARY_LLM_MODEL", validation_alias="PRIMARY_LLM_MODEL")
    strong_llm_model: str = Field(default="gpt-4o", alias="STRONG_LLM_MODEL", validation_alias="STRONG_LLM_MODEL")
    fast_llm_model: str = Field(default="gpt-4o-mini", alias="FAST_LLM_MODEL", validation_alias="FAST_LLM_MODEL")

    # Embeddings
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL", validation_alias="EMBEDDING_MODEL")
    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER", validation_alias="EMBEDDING_PROVIDER")

    # Upload / Security
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB", validation_alias="MAX_UPLOAD_SIZE_MB")
    max_files_in_archive: int = Field(default=5000, alias="MAX_FILES_IN_ARCHIVE", validation_alias="MAX_FILES_IN_ARCHIVE")
    max_single_file_size_mb: int = Field(default=10, alias="MAX_SINGLE_FILE_SIZE_MB", validation_alias="MAX_SINGLE_FILE_SIZE_MB")
    secret_key: str = Field(default="changeme", alias="SECRET_KEY", validation_alias="SECRET_KEY")
    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="ALLOWED_ORIGINS", validation_alias="ALLOWED_ORIGINS",
    )

    # Analysis
    workspace_dir: str = Field(default="./workspaces", alias="WORKSPACE_DIR", validation_alias="WORKSPACE_DIR")
    sandbox_timeout_seconds: int = Field(default=30, alias="SANDBOX_TIMEOUT_SECONDS", validation_alias="SANDBOX_TIMEOUT_SECONDS")
    enable_sandbox_execution: bool = Field(default=False, alias="ENABLE_SANDBOX_EXECUTION", validation_alias="ENABLE_SANDBOX_EXECUTION")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def max_single_file_size_bytes(self) -> int:
        return self.max_single_file_size_mb * 1024 * 1024


settings = Settings()
