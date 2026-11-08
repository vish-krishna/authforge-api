"""Secrets and runtime configuration management module for AuthForge."""

import os
from typing import Any

from dotenv import load_dotenv

from src.logger import logger



load_dotenv()


class SecretStore:
    """Singleton store managing local environment variables and remote secrets."""

    def __init__(self) -> None:
        # Internal secrets dictionary cache
        self._secrets: dict[str, Any] = {}
        # Track initialization state to make loading idempotent
        self._is_loaded: bool = False

    def load_secrets(self) -> None:
        """Loads environment variables and configuration secrets into memory."""
        # Prevent re-loading if already initialized
        if self._is_loaded:
            return

        logger.info("Loading application configuration and secrets...")

        # Resolve discrete database settings
        db_name = os.getenv("DB_NAME", "")
        db_user = os.getenv("DB_USER", "")
        db_host = os.getenv("DB_HOST", "localhost")
        raw_port = os.getenv("DB_PORT", "5432")
        db_password = os.getenv("DB_PASSWORD", "")

        # Safely parse DB_PORT to an integer with a fallback
        try:
            db_port = int(raw_port)
        except ValueError:
            logger.warning(
                f"Invalid DB_PORT value '{raw_port}'. Falling back to default port 5432."
            )
            db_port = 5432

        # Cache credentials into internal store
        self._secrets.update(
            {
                "DATABASE_URL": os.getenv("DATABASE_URL"),
                "DB_NAME": db_name,
                "DB_USER": db_user,
                "DB_HOST": db_host,
                "DB_PORT": db_port,
                "DB_PASSWORD": db_password,
                "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-prod"),
                "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            }
        )

        self._is_loaded = True
        logger.info("Secrets loaded successfully.")

    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like accessor compatible with SECRETS.get('KEY')."""
        if not self._is_loaded:
            self.load_secrets()
        return self._secrets.get(key, default)

    # -------------------------------------------------------------------------
    # Typed Property Accessors
    # -------------------------------------------------------------------------
    @property
    def DB_NAME(self) -> str:
        """The target database name."""
        return self.get("DB_NAME", "")

    @property
    def DB_USER(self) -> str:
        """The database username."""
        return self.get("DB_USER", "")

    @property
    def DB_HOST(self) -> str:
        """The database hostname or IP address."""
        return self.get("DB_HOST", "localhost")

    @property
    def DB_PORT(self) -> int:
        """The database connection port."""
        return self.get("DB_PORT", 5432)

    @property
    def DB_PASSWORD(self) -> str:
        """The database password."""
        return self.get("DB_PASSWORD", "")

    @property
    def DATABASE_URL(self) -> str | None:
        """Full database connection string if provided directly."""
        return self.get("DATABASE_URL")

    @property
    def JWT_SECRET_KEY(self) -> str:
        """JWT secret key used for signing tokens."""
        return self.get("JWT_SECRET_KEY", "")

    @property
    def LOG_LEVEL(self) -> str:
        """Log level string (e.g., 'DEBUG', 'INFO')."""
        return self.get("LOG_LEVEL", "INFO")


# Global singleton instance
SECRETS = SecretStore()

__all__ = ["SECRETS", "SecretStore"]