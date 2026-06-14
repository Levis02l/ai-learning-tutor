from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tutor:tutor@localhost:5432/tutor"
    anthropic_api_key: str = ""
    openai_api_key: str = ""


settings = Settings()
