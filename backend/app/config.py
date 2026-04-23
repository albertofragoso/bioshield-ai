from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "BioShield AI"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./bioshield.db"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Encryption (AES-256)
    aes_key: str = "dev-aes-key-32-bytes-changethis!"  # Must be exactly 32 bytes

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_db"
    chroma_collection_name: str = "bioshield_ingredients"

    # Embeddings fallback
    use_local_embeddings: bool = False
    bge_model_name: str = "BAAI/bge-m3"

    # Open Food Facts — read
    off_base_url: str = "https://world.openfoodfacts.org/api/v2"
    off_timeout_seconds: int = 10

    # Open Food Facts — write (flujo contributivo, Fase 2)
    off_write_base_url: str = "https://world.openfoodfacts.org/cgi"
    off_app_name: str = "BioShieldAI"
    off_app_version: str = "1.0"
    off_contributor_user: str = ""       # cuenta registrada en world.openfoodfacts.org
    off_contributor_password: str = ""   # password de la cuenta contributora
    off_contrib_enabled: bool = False    # feature flag — False en dev por defecto
    off_contrib_timeout_seconds: int = 15
    off_contrib_sync_for_tests: bool = False  # ejecutar background task sincrónicamente en pytest

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
