from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    app_name: str = "Face Image Detection API"
    mongo_uri: str = Field(default="mongodb://localhost:27017", alias="MONGO_URI")
    mongo_db_name: str = Field(default="face_finder", alias="MONGO_DB_NAME")
    mongo_collection_name: str = Field(default="photos", alias="MONGO_COLLECTION_NAME")
    media_root: Path = Field(default=Path("backend/media"), alias="MEDIA_ROOT")
    media_url_prefix: str = Field(default="/media", alias="MEDIA_URL_PREFIX")
    face_distance_threshold: float = Field(default=0.6, alias="FACE_DISTANCE_THRESHOLD")
    allow_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:4200"],
        alias="ALLOW_ORIGINS",
    )
    max_results: int = Field(default=100, alias="MAX_RESULTS")
    dataset_path: Optional[Path] = Field(default=Path("/Users/aanand/Downloads/Collection"), alias="DATASET_PATH")
    dataset_labels: List[str] = Field(default_factory=list, alias="DATASET_LABELS")
    search_distance_multiplier: float = Field(default=0.92, alias="SEARCH_DISTANCE_MULTIPLIER")
    person_id_distance_multiplier: float = Field(default=0.9, alias="PERSON_ID_DISTANCE_MULTIPLIER")
    auto_ingest_on_startup: bool = Field(default=True, alias="AUTO_INGEST_ON_STARTUP")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    @field_validator("allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("dataset_labels", mode="before")
    @classmethod
    def _split_labels(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("search_distance_multiplier", "person_id_distance_multiplier", mode="before")
    @classmethod
    def _normalize_multiplier(cls, value: float) -> float:
        if not value:
            return 1.0
        return max(0.01, min(float(value), 1.0))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.media_root = Path(settings.media_root)
    if settings.dataset_path:
        settings.dataset_path = Path(settings.dataset_path)
    return settings
