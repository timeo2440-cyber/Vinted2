from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/vinted_bot.db"
    secret_key: str = "change-me-in-production"
    frontend_dir: str = str(BASE_DIR / "frontend")
    vinted_base_url: str = "https://www.vinted.fr"
    vinted_api_base: str = "https://www.vinted.fr/api/v2"
    default_poll_interval_ms: int = 4000
    default_max_buy_per_hour: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
