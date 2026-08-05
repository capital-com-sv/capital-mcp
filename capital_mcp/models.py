"""Core data models for Capital.com MCP Server."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def _validate_iso_good_till_date(value: str | None) -> str | None:
    """Reject non-ISO 8601 values upfront so the LLM sees the error before
    a preview-confirm round-trip ends with HTTP 400 from the broker."""
    if value is None:
        return value
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"good_till_date must be ISO 8601 UTC (e.g. 2026-08-15T14:30:00); got {value!r}"
        ) from exc
    return value


# Field description constants
EPIC_DESCRIPTION = "Market EPIC"
CONFIRM_DESCRIPTION = "Explicit confirmation"
DESC_STOP_LEVEL = "Stop loss level"
DESC_STOP_DISTANCE = "Stop loss distance"
DESC_STOP_AMOUNT = "Stop loss amount"
DESC_PROFIT_LEVEL = "Take profit level"
DESC_PROFIT_DISTANCE = "Take profit distance"
DESC_PROFIT_AMOUNT = "Take profit amount"

# ============================================================
# Enums
# ============================================================


class Direction(str, Enum):
    """Trade direction."""

    BUY = "BUY"
    SELL = "SELL"


class WorkingOrderType(str, Enum):
    """Working order type."""

    LIMIT = "LIMIT"
    STOP = "STOP"


class TimeInForce(str, Enum):
    """Working order time-in-force."""

    GOOD_TILL_CANCELLED = "GOOD_TILL_CANCELLED"
    GOOD_TILL_DATE = "GOOD_TILL_DATE"


class PriceResolution(str, Enum):
    """Price resolution for historical data."""

    MINUTE = "MINUTE"
    MINUTE_5 = "MINUTE_5"
    MINUTE_15 = "MINUTE_15"
    MINUTE_30 = "MINUTE_30"
    HOUR = "HOUR"
    HOUR_4 = "HOUR_4"
    DAY = "DAY"
    WEEK = "WEEK"


# ============================================================
# Standard Result Wrapper
# ============================================================


class ToolMeta(BaseModel):
    """Metadata for tool results."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    ts: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


class ToolError(BaseModel):
    """Error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")


class ToolResult(BaseModel):
    """Standard tool result wrapper."""

    ok: bool = Field(..., description="Success status")
    data: dict[str, Any] | None = Field(default=None, description="Result data")
    error: ToolError | None = Field(default=None, description="Error information")
    meta: ToolMeta = Field(default_factory=ToolMeta)

    @classmethod
    def success(cls, data: dict[str, Any]) -> "ToolResult":
        """Create a successful result."""
        return cls(ok=True, data=data, error=None)

    @classmethod
    def failure(
        cls, code: str, message: str, details: dict[str, Any] | None = None
    ) -> "ToolResult":
        """Create a failed result."""
        return cls(
            ok=False, data=None, error=ToolError(code=code, message=message, details=details)
        )


# ============================================================
# Session Models
# ============================================================


class SessionTokens(BaseModel):
    """Session authentication tokens."""

    cst: str = Field(..., description="CST authorization token")
    x_security_token: str = Field(..., description="X-SECURITY-TOKEN account token")
    last_used_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, max_age_seconds: int = 540) -> bool:
        """Check if session is likely expired (9 minutes default)."""
        age = (datetime.now(timezone.utc) - self.last_used_at).total_seconds()
        return age >= max_age_seconds

    def update_last_used(self) -> None:
        """Update the last used timestamp."""
        self.last_used_at = datetime.now(timezone.utc)


class SessionStatus(BaseModel):
    """Session status information."""

    env: str
    base_url: str
    logged_in: bool
    account_id: str | None = None
    last_used_at: str | None = None
    expires_in_s_estimate: int | None = None


# ============================================================
# Market Data Models
# ============================================================


class MarketSearchRequest(BaseModel):
    """Request for market search."""

    search_term: str | None = Field(default=None, description="Search term")
    epics: list[str] | None = Field(default=None, description="List of EPICs to filter")
    limit: int = Field(default=50, ge=1, le=1000, description="Max results")


class MarketGetRequest(BaseModel):
    """Request for market details."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)


class PricesRequest(BaseModel):
    """Request for historical prices."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)
    resolution: PriceResolution = Field(default=PriceResolution.MINUTE_15)
    max: int = Field(default=200, ge=1, le=1000, description="Max candles")
    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")


# ============================================================
# Trading Models
# ============================================================


class PreviewPositionRequest(BaseModel):
    """Request to preview a position."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)
    direction: Direction = Field(..., description="Trade direction")
    size: float = Field(..., gt=0, description="Position size")
    guaranteed_stop: bool = Field(default=False, description="Use guaranteed stop")
    trailing_stop: bool = Field(default=False, description="Use trailing stop")
    stop_level: float | None = Field(default=None, description=DESC_STOP_LEVEL)
    stop_distance: float | None = Field(default=None, description=DESC_STOP_DISTANCE)
    stop_amount: float | None = Field(default=None, description=DESC_STOP_AMOUNT)
    profit_level: float | None = Field(default=None, description=DESC_PROFIT_LEVEL)
    profit_distance: float | None = Field(default=None, description=DESC_PROFIT_DISTANCE)
    profit_amount: float | None = Field(default=None, description=DESC_PROFIT_AMOUNT)


class PreviewWorkingOrderRequest(BaseModel):
    """Request to preview a working order."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)
    direction: Direction = Field(..., description="Trade direction")
    type: WorkingOrderType = Field(..., description="Order type")
    level: float = Field(..., description="Order trigger level")
    size: float = Field(..., gt=0, description="Order size")
    guaranteed_stop: bool = Field(default=False, description="Use guaranteed stop")
    trailing_stop: bool = Field(default=False, description="Use trailing stop")
    stop_level: float | None = Field(default=None, description=DESC_STOP_LEVEL)
    stop_distance: float | None = Field(default=None, description=DESC_STOP_DISTANCE)
    stop_amount: float | None = Field(default=None, description=DESC_STOP_AMOUNT)
    profit_level: float | None = Field(default=None, description=DESC_PROFIT_LEVEL)
    profit_distance: float | None = Field(default=None, description=DESC_PROFIT_DISTANCE)
    profit_amount: float | None = Field(default=None, description=DESC_PROFIT_AMOUNT)
    good_till_date: str | None = Field(
        default=None,
        description="Good till date in ISO 8601 UTC (e.g. 2026-08-15T14:30:00)",
    )

    _validate_good_till_date = field_validator("good_till_date")(_validate_iso_good_till_date)


class UpdateWorkingOrderRequest(BaseModel):
    """Request to update a pending working order."""

    deal_id: str = Field(..., description="Deal ID of the working order to update")
    level: float | None = Field(default=None, gt=0, description="New order trigger level")
    stop_level: float | None = Field(default=None, gt=0, description=DESC_STOP_LEVEL)
    stop_distance: float | None = Field(default=None, gt=0, description=DESC_STOP_DISTANCE)
    stop_amount: float | None = Field(default=None, gt=0, description=DESC_STOP_AMOUNT)
    profit_level: float | None = Field(default=None, gt=0, description=DESC_PROFIT_LEVEL)
    profit_distance: float | None = Field(default=None, gt=0, description=DESC_PROFIT_DISTANCE)
    profit_amount: float | None = Field(default=None, gt=0, description=DESC_PROFIT_AMOUNT)
    good_till_date: str | None = Field(
        default=None,
        description="Good till date in ISO 8601 UTC (e.g. 2026-08-15T14:30:00)",
    )
    time_in_force: TimeInForce | None = Field(
        default=None,
        description=(
            "Time in force — GOOD_TILL_CANCELLED clears any expiry, "
            "GOOD_TILL_DATE requires good_till_date. None preserves existing."
        ),
    )
    # None means "carry forward existing value" — Capital.com resets omitted flags to false
    guaranteed_stop: bool | None = Field(default=None, description="Guaranteed stop flag")
    trailing_stop: bool | None = Field(default=None, description="Trailing stop flag")

    _validate_good_till_date = field_validator("good_till_date")(_validate_iso_good_till_date)


class RiskCheck(BaseModel):
    """Individual risk check result."""

    check: str = Field(..., description="Check name")
    passed: bool = Field(..., description="Check passed")
    message: str = Field(..., description="Check message")


class PreviewResult(BaseModel):
    """Result of a preview operation."""

    preview_id: str = Field(default_factory=lambda: str(uuid4()))
    normalized_request: dict[str, Any] = Field(..., description="Normalized request data")
    checks: list[RiskCheck] = Field(..., description="Risk checks performed")
    all_checks_passed: bool = Field(..., description="All checks passed")
    estimated_entry: float | None = Field(default=None, description="Estimated entry price")
    estimated_risk_notes: str | None = Field(default=None, description="Risk estimation notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, ttl_seconds: int = 120) -> bool:
        """Check if preview has expired (2 minutes default)."""
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age >= ttl_seconds


class ExecutePositionRequest(BaseModel):
    """Request to execute a position."""

    preview_id: str = Field(..., description="Preview ID from preview operation")
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)
    wait_for_confirm: bool = Field(default=True, description="Wait for broker confirmation")
    timeout_s: float = Field(default=15.0, gt=0, description="Confirmation timeout")


class ExecuteWorkingOrderRequest(BaseModel):
    """Request to execute a working order."""

    preview_id: str = Field(..., description="Preview ID from preview operation")
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)
    wait_for_confirm: bool = Field(default=True, description="Wait for broker confirmation")
    timeout_s: float = Field(default=15.0, gt=0, description="Confirmation timeout")


class ConfirmWaitRequest(BaseModel):
    """Request to wait for confirmation."""

    deal_reference: str = Field(..., description="Deal reference from trade operation")
    timeout_s: float = Field(default=15.0, gt=0, description="Timeout in seconds")
    poll_interval_ms: int = Field(default=500, ge=100, le=5000, description="Poll interval in ms")


# ============================================================
# Account Models
# ============================================================


class AccountPreferencesSetRequest(BaseModel):
    """Request to set account preferences."""

    hedging_mode: bool | None = Field(default=None, description="Enable hedging mode")
    leverages: dict[str, int | None] | None = Field(
        default=None, description="Leverage settings per asset class"
    )
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)


class DemoTopUpRequest(BaseModel):
    """Request to top up demo account."""

    amount: float = Field(..., gt=0, description="Amount to add")
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)


# ============================================================
# Watchlist Models
# ============================================================


class WatchlistCreateRequest(BaseModel):
    """Request to create a watchlist."""

    name: str = Field(..., min_length=1, max_length=100, description="Watchlist name")
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)


class WatchlistAddMarketRequest(BaseModel):
    """Request to add market to watchlist."""

    watchlist_id: str = Field(..., description="Watchlist ID")
    epic: str = Field(..., description=EPIC_DESCRIPTION)
    confirm: bool = Field(default=False, description=CONFIRM_DESCRIPTION)


# ============================================================
# WebSocket Streaming Models
# ============================================================


class PriceTick(BaseModel):
    """WebSocket price update."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)
    bid: float = Field(..., description="Bid price")
    offer: float = Field(..., description="Offer/ask price")
    timestamp: str = Field(..., description="Update timestamp (ISO 8601)")
    change_percent: float | None = Field(default=None, description="Price change percentage")


class StreamAlert(BaseModel):
    """Alert trigger event."""

    epic: str = Field(..., description=EPIC_DESCRIPTION)
    condition: str = Field(..., description="Alert condition (LEVEL_ABOVE, LEVEL_BELOW, BREAKOUT)")
    trigger_price: float = Field(..., description="Price that triggered the alert")
    current_price: float = Field(..., description="Current market price")
    timestamp: str = Field(..., description="Alert timestamp (ISO 8601)")


class PortfolioSnapshot(BaseModel):
    """Real-time portfolio state."""

    positions: list[dict[str, Any]] = Field(..., description="List of open positions")
    total_pnl: float = Field(..., description="Total portfolio P&L")
    timestamp: str = Field(..., description="Snapshot timestamp (ISO 8601)")
