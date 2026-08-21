from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    bot_token: str = ""
    admin_password: str = "admin123"
    db_path: str = "docuflow.db"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    free_docs_limit: int = 5
    max_template_fields: int = 20

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", "admin123"),
            db_path=os.getenv("DB_PATH", "docuflow.db"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            free_docs_limit=int(os.getenv("FREE_DOCS_LIMIT", "5")),
        )
