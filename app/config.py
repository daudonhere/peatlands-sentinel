from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Peatlands Sentinel"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Data directory
    data_dir: Path = Path("data")

    # STAC Providers
    stac_api_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac"

    # AI Analyst Configuration (Custom, OpenAI-compatible, or Ollama)
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_provider: str = "custom"  # "custom", "openai", "ollama"

    # Local Ollama fallback
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
