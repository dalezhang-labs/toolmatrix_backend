import os
from pydantic_settings import BaseSettings
from typing import Optional


class OmnigaTechSettings(BaseSettings):
    # Database: prefer OMNIGATECH_DATABASE_URL, fall back to DATABASE_URL
    omnigatech_database_url: Optional[str] = os.getenv("OMNIGATECH_DATABASE_URL")
    database_url: str = os.getenv("DATABASE_URL", "")

    @property
    def effective_database_url(self) -> str:
        """Return the database URL to use, with fallback logic."""
        return self.omnigatech_database_url or self.database_url

    # Stripe
    stripe_secret_key: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")

    # Email (Resend)
    resend_api_key: Optional[str] = os.getenv("RESEND_API_KEY")
    email_from: str = os.getenv("EMAIL_FROM", "noreply@omnigatech.com")

    # Auth
    omnigatech_secret_key: str = os.getenv("OMNIGATECH_SECRET_KEY", "omnigatech-dev-secret")

    # Frontend
    frontend_url: str = os.getenv(
        "OMNIGATECH_FRONTEND_URL", "https://zendesk.omnigatech.com"
    )

    # Debug
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    class Config:
        env_file = ".env"


omnigatech_settings = OmnigaTechSettings()
