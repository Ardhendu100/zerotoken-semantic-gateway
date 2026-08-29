from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    UPSTREAM_BASE_URL: str = "https://api.groq.com/openai/v1"
    UPSTREAM_API_KEY: str = ""
    UPSTREAM_MODEL: str = "openai/gpt-oss-20b"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()