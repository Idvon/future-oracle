from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FO_")

    app_name: str = "Future Oracle"
    database_url: str = "sqlite:///./future_oracle.db"

    wikipedia_page: str = "2026 in video games"

    rss_feeds: list[str] = [
        "https://www.gamespot.com/feeds/news/",
        "https://www.eurogamer.net/feed",
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
    ]

    stores: list[dict] = [
        {
            "name": "Epic Games Store",
            "kind": "store",
            "url": "https://store.epicgames.com",
            "reliability": 0.7,
            "type": "epic",
        },
        {
            "name": "GOG",
            "kind": "store",
            "url": "https://www.gog.com",
            "reliability": 0.7,
            "type": "gog",
        },
        {
            "name": "Steam Store",
            "kind": "store",
            "url": "https://store.steampowered.com",
            "reliability": 0.8,
            "type": "steam",
        },
    ]

    enable_scheduler: bool = False
    collect_interval_minutes: int = 60

    signal_weights: dict[str, float] = {
        "official_date_confirmed": 1.0,
        "rating_board_listing": 0.8,
        "preorder_open": 0.7,
        "dev_phase": 0.6,
        "news_mention_recent": 0.4,
        "silent_period": -0.5,
        "delay_history": -0.6,
    }

    signal_labels: dict[str, str] = {
        "official_date_confirmed": "Official date confirmed",
        "rating_board_listing": "Rating board listing (ESRB/PEGI)",
        "preorder_open": "Pre-orders open",
        "dev_phase": "Development phase in news",
        "news_mention_recent": "Recent press mentions",
        "silent_period": "No news for a long time",
        "delay_history": "Studio/franchise delay history",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
