from decimal import Decimal
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/autoreconcile"
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AUTO_MATCH_THRESHOLD: float = 0.85
    BORDERLINE_LOWER: float = 0.65
    AMOUNT_TOLERANCE: Decimal = Decimal("0.01")
    DATE_TOLERANCE_DAYS: int = 3
    MERCHANT_SIMILARITY_THRESHOLD: float = 0.75
    RRF_K: int = 60
    LEXICAL_WEIGHT: float = 2.0
    SEMANTIC_WEIGHT: float = 1.0
    GEMINI_TIMEOUT_SECONDS: float = 10.0
    MAX_GEMINI_RETRIES: int = 2
    GEMINI_CONCURRENCY: int = 5

    @property
    def is_gemini_configured(self) -> bool:
        return bool(self.GOOGLE_API_KEY and self.GOOGLE_API_KEY.strip() and self.GEMINI_MODEL and self.GEMINI_MODEL.strip())


@lru_cache()
def get_settings() -> Settings:
    return Settings()
