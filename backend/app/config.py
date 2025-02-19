import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional

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
    pandaetl_server_url: str = "https://api.panda-etl.ai/"
    log_file_path: str = os.path.join(os.path.dirname(__file__), "..", "pandaetl.log")
    max_retries: int = 3
    max_relevant_docs: int = 10
    max_file_size: int = 20 * 1024 * 1024
    chroma_batch_size: int = 5

    # OpenAI embeddings config
    use_openai_embeddings: bool = False
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-ada-002"

    # Extraction References for chat
    chat_extraction_doc_threshold: float = 0.5
    chat_extraction_max_docs: int = 50

    # PandaETL api key
    pandaetl_api_key: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
