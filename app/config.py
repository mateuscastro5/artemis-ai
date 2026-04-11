from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "pr_complexity_examples"

    gemini_api_key: str = ""
    openai_api_key: str = ""

    # Local LLM via Ollama (fallback when Gemini/OpenAI are unavailable)
    ollama_url: str = "http://ollama:11434"
    llm_local_model: str = "deepseek-coder:6.7b"

    embedding_model: str = "all-MiniLM-L6-v2"
    llm_reader_model: str = "gemini-2.0-flash"
    llm_scorer_model: str = "gemini-2.0-pro"

    confidence_threshold: float = 0.7
    max_diff_lines: int = 3000

    nestjs_callback_url: str = "http://localhost:3000"

    internal_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
