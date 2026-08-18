"""Configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDSYNC_", env_file=".env", extra="ignore")

    state_db: str = ".embedsync/state.db"
    log_level: str = "INFO"
    dry_run: bool = False
