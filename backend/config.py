import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:1b"
    backend_port: int = 8000
    log_file: str = os.path.join(os.path.dirname(__file__), "logs", "app.log")
    faq_data_path: str = os.path.join(os.path.dirname(__file__), "faq_data.json")
    database_url: str = "sqlite:///./chat_history.db"
    max_document_bytes: int = 512_000
    allowed_document_extensions: tuple[str, ...] = (".txt", ".md")
    # Optional production .env fields (ignored if unused)
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production-use-a-long-random-string"

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False,
        env_file=_ENV_FILE,
        extra="ignore",
    )


settings = Settings()
