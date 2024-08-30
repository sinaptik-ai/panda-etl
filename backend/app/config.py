import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    sqlalchemy_database_url: str
    chromadb_url: str = os.path.join(
        os.path.dirname(__file__), "..", "instance", "chromadb"
    )
    upload_dir: str = os.path.join(os.path.dirname(__file__), "..", "uploads")
    process_dir: str = os.path.join(os.path.dirname(__file__), "..", "processed")
    api_server_url: str = "https://api.domer.ai"
    pandaetl_server_url: str
    log_file_path: str = os.path.join(os.path.dirname(__file__), "..", "pandaetl.log")
    openai_api_key: str
    ai_model: str = "gpt-4o-mini"
    max_retries: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
