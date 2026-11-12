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

    data_dir: Path = Path("data")

    data_source: str = "planetary_computer"

    stac_api_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac"

    firms_map_key: str = ""

    gee_project: str = ""
    gee_service_account: str = ""
    gee_private_key_file: Path | None = None
    gee_worldcover_collection: str = "ESA/WorldCover/v200/2021"
    gee_samples_per_class: int = 150
    gee_rf_trees: int = 200

    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_provider: str = "openai"
    ai_timeout_seconds: float = 25.0

    ollama_api_key: str = ""
    ollama_url: str = "https://ollama.com/api/chat"
    ollama_model: str = "beam:cloud"

    @property
    def ai_ready(self) -> bool:
        if self.ai_provider == "ollama":
            return bool(self.ollama_api_key and self.ollama_model)
        return bool(self.ai_api_key and self.ai_model)

    @property
    def gee_ready(self) -> bool:
        return bool(self.gee_project)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
