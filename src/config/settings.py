from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str = ""
    github_mcp_url: str = "https://api.githubcopilot.com/mcp/"

    github_client_id: str
    github_client_secret: str
    github_oauth_redirect_uri: str
    frontend_url: str = "http://localhost:8501"
    auth_encryption_key: str

    groq_api_key: str
    gemini_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str
    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()