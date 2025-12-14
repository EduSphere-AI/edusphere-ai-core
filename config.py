from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/edusphere",
        env="DATABASE_URL")

    # JWT Settings
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Firebase
    firebase_credentials_path: str = Field(default="firebase-credentials.json",
                                           env="FIREBASE_CREDENTIALS_PATH")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
