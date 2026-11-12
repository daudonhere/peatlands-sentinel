from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Peatlands Sentinel"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Planetary Computer STAC endpoint (public free access)
    stac_api_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"

    # Local AI Analyst
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
