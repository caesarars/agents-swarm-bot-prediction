from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_version: str = "2023-06-01"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_model: str = "gemini-2.5-flash"

    binance_api_key: str = ""
    binance_base_url: str = "https://api.binance.com"
    binance_futures_base_url: str = "https://fapi.binance.com"

    polymarket_api_key: str = ""
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_url: str = "https://clob.polymarket.com"

    database_url: str = "sqlite+aiosqlite:///./data/predictions.db"
    prediction_interval_minutes: int = 5
    agent_concurrency: int = 10
    agent_timeout_seconds: int = 45
    swarm_aggregation_mode: str = "primary_confirm"
    swarm_primary_provider: str = "deepseek"
    swarm_primary_min_margin: float = 1.5
    swarm_override_margin: float = 4.0
    swarm_deepseek_weight: float = 1.0
    swarm_anthropic_weight: float = 0.35
    swarm_gemini_weight: float = 0.0
    learning_enabled: bool = True
    learning_lookback: int = 200
    learning_min_agent_samples: int = 8
    learning_min_group_samples: int = 12
    learning_min_weight: float = 0.35
    learning_max_weight: float = 1.8
    learning_smoothing: float = 6.0
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
