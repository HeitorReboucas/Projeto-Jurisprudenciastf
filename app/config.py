from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Coletor de Jurisprudências STF"
    data_dir: Path = Path("data")
    stf_timeout_seconds: float = 90
    stf_request_delay_seconds: float = Field(default=1.0, ge=1.0)
    stf_max_attempts: int = 3
    stf_browser_channel: str | None = None
    download_max_bytes: int = 50 * 1024 * 1024
    download_timeout_seconds: float = 60
    google_client_secrets_file: Path = Path("credentials.json")
    google_token_file: Path | None = None
    google_redirect_uri: str = "http://localhost:8000/api/drive/oauth/callback"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jurisprudencias.sqlite3"

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    @property
    def token_path(self) -> Path:
        return self.google_token_file or self.data_dir / "google-token.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()