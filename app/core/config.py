from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"

    # Phase 1+
    qdrant_api_key: str = ""
    qdrant_cluster_endpoint: str = ""
    qdrant_collection_name: str = "bkip_docs"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    data_dir: str = "DATA"
    processed_data_dir: str = "processed_data"

    # Phase 2+
    groq_api_key: str = ""

    # Phase 5+
    portkey_api_key: str = ""
    portkey_config_id: str = ""
    groq_fallback_api_key: str = ""
    logfire_token: str = ""
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "bkip"

    # Phase 6+
    judge_groq_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
