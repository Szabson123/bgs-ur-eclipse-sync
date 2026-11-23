from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Eclipse (MS SQL) – te same nazwy zmiennych co w BGS-ur-analitycs, .env można skopiować
    eclipse_host: str = Field(alias="ECLIPSE_HOST")
    eclipse_user: str = Field(alias="ECLIPSE_USER")
    eclipse_password: str = Field(alias="ECLIPSE_PASSWORD")
    eclipse_database: str = Field(alias="ECLIPSE_NAME")

    # BGS-backend – adres bazowy (bez /api) i klucz serwisu (CYCLE_GUARD_ECLIPSE_API_KEY w .env backendu)
    bgs_url: str = Field("http://127.0.0.1:8000", alias="BGS_URL")
    bgs_api_key: str = Field(alias="BGS_API_KEY")

    sync_interval_seconds: int = Field(60, alias="SYNC_INTERVAL_SECONDS")
    # false = bez harmonogramu (testy, ręczne POST /sync/run)
    sync_enabled: bool = Field(True, alias="SYNC_ENABLED")
    request_timeout_seconds: float = Field(10, alias="REQUEST_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
