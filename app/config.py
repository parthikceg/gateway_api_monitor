"""Application configuration"""
from pydantic import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    database_url: str
    openai_api_key: str
    
    # Email settings (optional for MVP)
    email_provider: str = "sendgrid"
    sendgrid_api_key: str = ""
    alert_from_email: str = ""
    alert_from_name: str = "Gateway Monitor"
    
    # Monitoring settings
    crawl_schedule_hours: int = 24
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
