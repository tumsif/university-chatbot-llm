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

    class Config:
        env_prefix = "APP_"
        case_sensitive = False
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

settings = Settings()
