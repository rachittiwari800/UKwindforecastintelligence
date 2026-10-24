import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "UK Wind Forecast Intelligence"
    elexon_base_url: str = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
    default_cutoff: str = os.getenv("DEFAULT_CUTOFF", "11:00")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    cors_origins: List[str] = None
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    def __post_init__(self):
        if self.cors_origins is None:
            raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
            object.__setattr__(self, "cors_origins", [item.strip() for item in raw.split(",") if item.strip()])


settings = Settings()
