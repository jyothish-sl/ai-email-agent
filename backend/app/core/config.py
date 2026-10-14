"""
Application settings.

Loaded once from environment variables / .env via pydantic-settings.
Required secrets (JWT_SECRET_KEY, FERNET_KEY) have NO default — the app
will refuse to start if they are missing, instead of silently generating
a throwaway key that breaks every restart.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="", alias="LOG_LEVEL")

    # Either provide DATABASE_URL directly, or the DB_* parts below.
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    db_user: str | None = Field(default=None, alias="DB_USER")
    db_password: str | None = Field(default=None, alias="DB_PASSWORD")
    db_name: str | None = Field(default=None, alias="DB_NAME")
    db_host: str = Field(default="db", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")

    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    fernet_key: str = Field(..., alias="FERNET_KEY")

    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    streamlit_base_url: str | None = Field(default=None, alias="STREAMLIT_BASE_URL")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if not all([self.db_user, self.db_password, self.db_name]):
            raise ValueError(
                "Set DATABASE_URL, or all of DB_USER/DB_PASSWORD/DB_NAME, in the environment."
            )
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_log_level(self) -> str:
        if self.log_level:
            return self.log_level.upper()
        return "INFO" if self.environment == "production" else "DEBUG"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
