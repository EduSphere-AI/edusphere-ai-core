from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    # Database
    # We are using Firebase Firestore as the main database.

    # JWT Settings
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production", env="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Firebase
    firebase_credentials_path: str = Field(default="firebase-credentials.json",
                                           env="FIREBASE_CREDENTIALS_PATH")

    # Supabase
    supabase_url: str = Field(default="", env="SUPABASE_URL")
    supabase_key: str = Field(default="", env="SUPABASE_KEY")
    supabase_bucket: str = Field(default="images", env="SUPABASE_BUCKET")

    # Paths
    base_dir: str = os.path.dirname(os.path.abspath(__file__))
    output_dir: str = Field(default="output", env="OUTPUT_DIR")

    @property
    def input_file_path(self) -> str:
        return os.path.join(self.base_dir, "data", "input.pdf")

    @property
    def extraction_output_path(self) -> str:
        return os.path.join(self.base_dir, self.output_dir, "extraction",
                            "extraction_result.json")

    @property
    def extraction_images_dir(self) -> str:
        return os.path.join(self.base_dir, self.output_dir, "images")

    @property
    def summarization_output_dir(self) -> str:
        return os.path.join(self.base_dir, self.output_dir, "summarization")

    @property
    def generation_output_path(self) -> str:
        return os.path.join(self.base_dir, self.output_dir, "generation",
                            "presentation.md")

    @property
    def log_file_path(self) -> str:
        return os.path.join(self.base_dir, "logs", "edusphere-ai.log")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
