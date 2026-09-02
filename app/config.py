from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    groq_api_key: str = ""
    xai_api_key: str = ""
    extra_providers_json: str = ""
    database_url: str = "postgresql://gateway:gateway@localhost:5432/gateway"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000


settings = Settings()
