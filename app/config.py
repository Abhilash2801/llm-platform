from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    extra_providers_json: str = ""
    gateway_primary_provider: str = ""
    gateway_primary_model: str = ""
    gateway_secondary_provider: str = ""
    gateway_secondary_model: str = ""
    database_url: str = "postgresql://gateway:gateway@localhost:5432/gateway"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000


settings = Settings()
