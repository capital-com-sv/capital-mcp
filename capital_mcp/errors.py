"""Error codes and exception handling for Capital.com MCP Server."""

from typing import Any

from .models import ToolResult

# ============================================================
# Error Codes (from spec section 16)
# ============================================================


class ErrorCode:
    """Standard error codes."""

    # Configuration errors
    CONFIG_MISSING = "CONFIG_MISSING"
    CONFIG_INVALID = "CONFIG_INVALID"

    # Trading safety errors
    TRADING_DISABLED = "TRADING_DISABLED"
    DRY_RUN_ENABLED = "DRY_RUN_ENABLED"
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    EPIC_NOT_ALLOWED = "EPIC_NOT_ALLOWED"
    RISK_LIMIT = "RISK_LIMIT"

    # Session errors
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_NOT_INITIALIZED = "SESSION_NOT_INITIALIZED"
    AUTH_FAILED = "AUTH_FAILED"

    # Rate limiting
    RATE_LIMITED_LOCAL = "RATE_LIMITED_LOCAL"

    # Broker/upstream errors
    BROKER_REJECTED = "BROKER_REJECTED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"

    # Preview/execution errors
    PREVIEW_NOT_FOUND = "PREVIEW_NOT_FOUND"
    PREVIEW_EXPIRED = "PREVIEW_EXPIRED"
    PREVIEW_CHECKS_FAILED = "PREVIEW_CHECKS_FAILED"

    # General errors
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================
# Custom Exceptions
# ============================================================


class CapitalMCPError(Exception):
    """Base exception for Capital MCP errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_tool_result(self) -> ToolResult:
        """Convert exception to ToolResult."""
        return ToolResult.failure(code=self.code, message=self.message, details=self.details)


class ConfigError(CapitalMCPError):
    """Configuration error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.CONFIG_INVALID, message, details)


class TradingDisabledError(CapitalMCPError):
    """Trading is disabled."""

    def __init__(self, message: str = "Trading is disabled. Set CAP_ALLOW_TRADING=true to enable."):
        super().__init__(ErrorCode.TRADING_DISABLED, message)


class DryRunError(CapitalMCPError):
    """Dry-run mode is enabled."""

    def __init__(
        self,
        message: str = "Dry-run mode is enabled. All trade executions are blocked.",
    ):
        super().__init__(ErrorCode.DRY_RUN_ENABLED, message)


class ConfirmRequiredError(CapitalMCPError):
    """Explicit confirmation is required."""

    def __init__(self, message: str = "Explicit confirmation required. Set confirm=true."):
        super().__init__(ErrorCode.CONFIRM_REQUIRED, message)


class EpicNotAllowedError(CapitalMCPError):
    """Epic is not in the allowlist."""

    def __init__(self, epic: str, allowed: list[str]):
        message = f"Epic '{epic}' is not in the allowlist. Allowed: {', '.join(allowed) if allowed else 'none'}"
        super().__init__(
            ErrorCode.EPIC_NOT_ALLOWED,
            message,
            {"epic": epic, "allowed_epics": allowed},
        )


class RiskLimitError(CapitalMCPError):
    """Risk limit exceeded."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.RISK_LIMIT, message, details)


class SessionError(CapitalMCPError):
    """Session-related error."""

    def __init__(self, message: str, code: str = ErrorCode.SESSION_EXPIRED):
        super().__init__(code, message)


class RateLimitError(CapitalMCPError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please slow down your requests.",
        retry_after: float | None = None,
    ):
        details = {"retry_after_seconds": retry_after} if retry_after else None
        super().__init__(ErrorCode.RATE_LIMITED_LOCAL, message, details)


class BrokerError(CapitalMCPError):
    """Broker rejected the request."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.BROKER_REJECTED, message, details)


class UpstreamError(CapitalMCPError):
    """Upstream API error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        details: dict[str, Any] = {}
        if status_code is not None:
            details["status_code"] = status_code
        if response_body is not None:
            details["response_body"] = response_body
        super().__init__(ErrorCode.UPSTREAM_ERROR, message, details)


class PreviewError(CapitalMCPError):
    """Preview-related error."""

    def __init__(self, message: str, code: str = ErrorCode.PREVIEW_NOT_FOUND):
        super().__init__(code, message)


# ============================================================
# Error Helper Functions
# ============================================================


def handle_exception(exc: Exception) -> ToolResult:
    """Convert any exception to a ToolResult."""
    if isinstance(exc, CapitalMCPError):
        return exc.to_tool_result()

    # Unhandled exception
    import traceback

    return ToolResult.failure(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Internal error: {str(exc)}",
        details={"traceback": traceback.format_exc()},
    )


def redact_secrets(data: dict[str, Any], secret_keys: set[str] | None = None) -> dict[str, Any]:
    """Redact secret values from a dictionary."""
    if secret_keys is None:
        secret_keys = {
            "cap_api_key",
            "cap_api_password",
            "password",
            "encryptedPassword",
            "cst",
            "x_security_token",
            "CST",
            "X-SECURITY-TOKEN",
            "X-CAP-API-KEY",
        }

    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if any(secret in key.lower() for secret in ["password", "token", "key", "secret", "cst"]):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value, secret_keys)
        elif isinstance(value, list):
            redacted[key] = [
                redact_secrets(item, secret_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted
