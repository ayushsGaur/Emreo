from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Ambulance Emergency Response Optimizer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Database ─────────────────────────────────────────────────
    # DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ambulance_db"
    DATABASE_URL: str = "sqlite+aiosqlite:///./ambulance.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_SECONDS: int = 300  # ambulance state expires after 5 min silence

    # ── ML Model ─────────────────────────────────────────────────
    MODEL_PATH: Path = Path("ml/models/severity_v1.pkl")
    MODEL_VERSION: str = "v1"
    SEVERITY_CONFIDENCE_THRESHOLD: float = 0.6  # below this → flag for human review

    # ── GIS / Routing ────────────────────────────────────────────
    OSRM_BASE_URL: str = "http://router.project-osrm.org"  # swap to self-hosted in prod
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    MAX_AMBULANCE_SEARCH_RADIUS_KM: float = 50.0

    # ── WebSocket ────────────────────────────────────────────────
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    GPS_UPDATE_INTERVAL: int = 5     # how often ambulances push location

    # ── Security ─────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    API_KEY_HEADER: str = "X-API-Key"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | text

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance — loaded once at startup.
    Use as a FastAPI dependency: settings = Depends(get_settings)
    """
    return Settings()


settings = get_settings()
