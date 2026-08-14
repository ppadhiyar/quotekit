from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure OpenAI (AI Foundry)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "quotekit-items"

    # Azure Document Intelligence (optional)
    azure_docintel_endpoint: str = ""
    azure_docintel_api_key: str = ""

    # App behavior
    demo_mode: bool = False
    confidence_threshold: float = 0.6
    max_tokens_per_session: int = 8000
    rate_limit_per_minute: int = 10

    # Access control: public traffic gets canned demo responses; live LLM
    # calls require the access code, capped per day. Uploads need the admin key.
    access_code: str = ""
    admin_api_key: str = ""
    llm_daily_request_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
