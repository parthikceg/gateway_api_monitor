"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    # Database provider selection: 'aws' or 'railway'
    db_provider: str = os.environ.get("DB_PROVIDER", "railway")

    # AWS RDS PostgreSQL
    aws_database_url: str = os.environ.get("AWS_DATABASE_URL", "")

    # Railway PostgreSQL (backup)
    railway_database_url: str = os.environ.get("RAILWAY_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

    @property
    def database_url(self) -> str:
        """Get the active database URL based on provider selection"""
        if self.db_provider == "aws":
            return self.aws_database_url
        else:
            return self.railway_database_url

    openai_api_key: str = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    openai_base_url: str = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    
    # Email settings (Zoho SMTP)
    smtp_host: str = "smtp.zoho.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_from_email: str = ""
    alert_from_name: str = "Gateway Monitor"

    # Weekly digest day (0=Monday, 6=Sunday)
    weekly_digest_day: int = 0
    weekly_digest_hour: int = 9
    
    # Monitoring settings
    crawl_schedule_hours: int = 24
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()