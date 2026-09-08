from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str
    groq_api_key: str
    gemini_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str
    database_url: str
    mcp_server_url: str = "http://127.0.0.1:8001/mcp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()