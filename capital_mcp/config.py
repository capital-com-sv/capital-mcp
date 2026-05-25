"""Configuration management for Capital.com MCP Server."""

import logging
import time
from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CapEnv(str, Enum):
    """Capital.com environment."""

    DEMO = "demo"
    LIVE = "live"


# Get project root directory (parent of capital_mcp package)
_PROJECT_ROOT = Path(__file__).parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,  # Allow CAP_API_KEY to match cap_api_key
        extra="ignore",
    )

    # ============================================================
    # REQUIRED: API Credentials
    # ============================================================
    cap_env: CapEnv = Field(default=CapEnv.DEMO, description="Environment: demo or live")
    cap_api_key: str = Field(..., description="API Key from Capital.com")
    cap_identifier: str = Field(..., description="Login email")
    cap_api_password: str = Field(..., description="API Key custom password")

    # ============================================================
    # SAFETY: Trading Controls
    # ============================================================
    cap_allow_trading: bool = Field(default=False, description="Allow trading operations")
    cap_allowed_epics: str = Field(default="", description="Comma-separated allowlist of EPICs")
    cap_max_position_size: float = Field(default=1.0, gt=0, description="Max position size")
    cap_max_working_order_size: float = Field(
        default=1.0, gt=0, description="Max working order size"
    )
    cap_max_open_positions: int = Field(
        default=3, ge=0, description="Max open positions at any time"
    )
    cap_max_orders_per_day: int = Field(default=20, ge=0, description="Max orders per day")
    cap_require_explicit_confirm: bool = Field(
        default=True, description="Require confirm=true for trade operations"
    )
    cap_dry_run: bool = Field(default=False, description="Dry-run mode: refuse all executions")

    # ============================================================
    # OPTIONAL: Account & Session
    # ============================================================
    cap_default_account_id: str | None = Field(
        default=None, description="Default account ID after login"
    )
    cap_http_timeout_s: float = Field(default=15.0, gt=0, description="HTTP timeout in seconds")
    cap_log_level: str = Field(default="INFO", description="Log level")
    cap_ws_enabled: bool = Field(default=False, description="Enable WebSocket streaming")

    # Internal defaults (not configurable via env)
    cap_preview_cache_ttl_s: int = Field(default=120, description="Preview cache TTL (seconds)")
    cap_ping_interval_s: int = Field(default=480, description="Session ping interval (8 minutes)")

    @field_validator("cap_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper_v

    @model_validator(mode="after")
    def validate_trading_config(self) -> "Config":
        """Validate trading configuration consistency."""
        if self.cap_allow_trading and not self.cap_allowed_epics.strip():
            raise ValueError(
                "CAP_ALLOW_TRADING is true but CAP_ALLOWED_EPICS is empty. "
                "You must specify allowed EPICs for trading (or use 'ALL' for unrestricted)."
            )
        return self

    @property
    def base_url(self) -> str:
        """Get base URL based on environment."""
        if self.cap_env == CapEnv.DEMO:
            return "https://demo-api-capital.backend-capital.com"
        return "https://api-capital.backend-capital.com"

    @property
    def api_base_url(self) -> str:
        """Get full API base URL."""
        return f"{self.base_url}/api/v1"

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL."""
        return "wss://api-streaming-capital.backend-capital.com/connect"

    @property
    def allowed_epics_list(self) -> list[str]:
        """Get allowed EPICs as a list."""
        if not self.cap_allowed_epics.strip():
            return []
        return [epic.strip() for epic in self.cap_allowed_epics.split(",") if epic.strip()]

    def is_epic_allowed(self, epic: str) -> bool:
        """Check if an epic is in the allowlist."""
        if not self.cap_allow_trading:
            return False
        allowed = self.allowed_epics_list
        if not allowed:
            return False
        # Check for 'ALL' wildcard
        if allowed[0].upper() == "ALL":
            return True
        return epic.upper() in [e.upper() for e in allowed]

    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.cap_log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        # Use UTC timestamps to match MCP transport logs
        logging.Formatter.converter = time.gmtime

        # Set httpx logging to WARNING to reduce noise
        logging.getLogger("httpx").setLevel(logging.WARNING)


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()  # type: ignore
        _config.setup_logging()
    return _config


def reset_config() -> None:
    """Reset the global config instance (mainly for testing)."""
    global _config
    _config = None
