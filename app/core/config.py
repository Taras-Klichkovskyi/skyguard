from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SkyGuard API"
    app_env: str = "dev"
    log_level: str = "INFO"

    postgres_user: str = "skyguard"
    postgres_password: str = "change-me"
    postgres_db: str = "skyguard"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # Правила якості даних (SG-2)
    dq_max_distance_m: int = 100  # DQ-1
    dq_max_age_min: int = 30  # DQ-2

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
