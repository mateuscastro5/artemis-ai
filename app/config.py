from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "pr_complexity_examples"

    openrouter_api_key: str = ""
    llm_model: str = "minimax/minimax-m2.5:free"

    voyage_api_key: str = ""
    embedding_model: str = "voyage-code-3"
    embedding_dim: int = 1024

    mem0_api_key: str = ""

    confidence_threshold: float = 0.7
    max_diff_lines: int = 3000

    nestjs_callback_url: str = "http://localhost:3000"

    internal_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
