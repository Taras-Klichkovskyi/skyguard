from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-before-any-real-deployment"


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

    # Автентифікація (NFR-B2): короткий access-токен і довший refresh
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    # Версія тексту політики, на яку погоджується користувач
    consent_policy_version: str = "1.0"

    # Звідки дозволено звертатися браузерному клієнту (через кому)
    cors_origins: str = (
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173,http://localhost:8080,http://localhost:8085"
    )

    # Правила якості даних (SG-2)
    dq_max_distance_m: int = 100  # DQ-1
    dq_max_age_min: int = 30  # DQ-2
    dq_quorum_weight: int = 3  # DQ-3: сума ваг звітів, потрібна для зміни статусу
    dq_quorum_window_min: int = 15  # DQ-3: вікно, у якому збирається кворум

    # Захист від спаму звітами (NFR-B9)
    report_rate_limit: int = 3  # UC-02 EX4: не більше 3 звітів…
    report_rate_window_min: int = 5  # …за 5 хвилин від одного користувача
    # Як часто фонове завдання анулює звіти без кворуму; 0 — вимкнено
    sweep_interval_s: int = 60

    # Інтеграція з alerts.in.ua (SG-23: моніторинг повітряних тривог)
    alerts_in_ua_token: str | None = None
    alerts_in_ua_poll_interval_s: int = 15
    alerts_monitored_location_title: str = "Львівська область"
    alerts_monitored_location_uid: int = 27

    @model_validator(mode="after")
    def _no_dev_secret_outside_dev(self) -> "Settings":
        if self.app_env not in ("dev", "test") and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET має бути заданий явно, якщо APP_ENV не dev/test")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
