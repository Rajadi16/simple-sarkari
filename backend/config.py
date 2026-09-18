"""
JanVaani — Centralized application settings.

Loads from environment variables / .env file using Pydantic BaseSettings.
All backend-only secrets live here. Never expose these to the frontend.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # ─── Application ───
    app_env: str = "development"
    app_debug: bool = True

    # ─── MongoDB ───
    mongo_url: str = "mongodb://localhost:27017"
    db_name: str = "janvaani"

    # ─── AWS ───
    aws_enabled: bool = True
    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket: str = "janvaani-dev"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    polly_region: str = "ap-south-1"

    # ─── Auth ───
    reviewer_token: str = "change-me-to-a-strong-secret"
    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ─── Crawler ───
    # Descriptive bot UA — identifies us honestly while avoiding WAF keyword triggers.
    # PIB and similar sites using Akamai block generic "bot/crawler" strings.
    crawler_user_agent: str = (
        "Mozilla/5.0 (compatible; JanVaani/1.0; +https://janvaani.in/about)"
    )
    crawler_default_delay_seconds: int = 5
    crawler_max_page_size_mb: int = 10
    crawler_max_pdf_size_mb: int = 50
    crawler_request_timeout_seconds: int = 30

    model_config = {"env_file": str(Path(__file__).parent / ".env"), "env_file_encoding": "utf-8"}



@lru_cache
def get_settings() -> Settings:
    """Cached singleton — call this from dependencies, not raw Settings()."""
    return Settings()
