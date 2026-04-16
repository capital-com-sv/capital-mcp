"""Core data models for Capital.com MCP Server."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

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
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


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
    last_used_at: datetime = Field(default_factory=datetime.utcnow)

    def is_expired(self, max_age_seconds: int = 540) -> bool:
        """Check if session is likely expired (9 minutes default)."""
        age = (datetime.utcnow() - self.last_used_at).total_seconds()
        return age >= max_age_seconds

    def update_last_used(self) -> None:
        """Update the last used timestamp."""
        self.last_used_at = datetime.utcnow()


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

    epic: str = Field(..., description="Market EPIC")


class PricesRequest(BaseModel):
    """Request for historical prices."""

    epic: str = Field(..., description="Market EPIC")
    resolution: PriceResolution = Field(default=PriceResolution.MINUTE_15)
    max: int = Field(default=200, ge=1, le=1000, description="Max candles")
    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")


# ============================================================
# Trading Models
# ============================================================


class PreviewPositionRequest(BaseModel):
    """Request to preview a position."""

    epic: str = Field(..., description="Market EPIC")
    direction: Direction = Field(..., description="Trade direction")
    size: float = Field(..., gt=0, description="Position size")
    guaranteed_stop: bool = Field(default=False, description="Use guaranteed stop")
    trailing_stop: bool = Field(default=False, description="Use trailing stop")
    stop_level: float | None = Field(default=None, description="Stop loss level")
    stop_distance: float | None = Field(default=None, description="Stop loss distance")
    stop_amount: float | None = Field(default=None, description="Stop loss amount")
    profit_level: float | None = Field(default=None, description="Take profit level")
    profit_distance: float | None = Field(default=None, description="Take profit distance")
    profit_amount: float | None = Field(default=None, description="Take profit amount")


class PreviewWorkingOrderRequest(BaseModel):
    """Request to preview a working order."""

    epic: str = Field(..., description="Market EPIC")
    direction: Direction = Field(..., description="Trade direction")
    type: WorkingOrderType = Field(..., description="Order type")
    level: float = Field(..., description="Order trigger level")
    size: float = Field(..., gt=0, description="Order size")
    guaranteed_stop: bool = Field(default=False, description="Use guaranteed stop")
    trailing_stop: bool = Field(default=False, description="Use trailing stop")
    stop_level: float | None = Field(default=None, description="Stop loss level")
    stop_distance: float | None = Field(default=None, description="Stop loss distance")
    stop_amount: float | None = Field(default=None, description="Stop loss amount")
    profit_level: float | None = Field(default=None, description="Take profit level")
    profit_distance: float | None = Field(default=None, description="Take profit distance")
    profit_amount: float | None = Field(default=None, description="Take profit amount")
    good_till_date: str | None = Field(default=None, description="Good till date (ISO 8601)")


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
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def is_expired(self, ttl_seconds: int = 120) -> bool:
        """Check if preview has expired (2 minutes default)."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age >= ttl_seconds


class ExecutePositionRequest(BaseModel):
    """Request to execute a position."""

    preview_id: str = Field(..., description="Preview ID from preview operation")
    confirm: bool = Field(default=False, description="Explicit confirmation")
    wait_for_confirm: bool = Field(default=True, description="Wait for broker confirmation")
    timeout_s: float = Field(default=15.0, gt=0, description="Confirmation timeout")


class ExecuteWorkingOrderRequest(BaseModel):
    """Request to execute a working order."""

    preview_id: str = Field(..., description="Preview ID from preview operation")
    confirm: bool = Field(default=False, description="Explicit confirmation")
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
    confirm: bool = Field(default=False, description="Explicit confirmation")


class DemoTopUpRequest(BaseModel):
    """Request to top up demo account."""

    amount: float = Field(..., gt=0, description="Amount to add")
    confirm: bool = Field(default=False, description="Explicit confirmation")


# ============================================================
# Watchlist Models
# ============================================================


class WatchlistCreateRequest(BaseModel):
    """Request to create a watchlist."""

    name: str = Field(..., min_length=1, max_length=100, description="Watchlist name")
    confirm: bool = Field(default=False, description="Explicit confirmation")


class WatchlistAddMarketRequest(BaseModel):
    """Request to add market to watchlist."""

    watchlist_id: str = Field(..., description="Watchlist ID")
    epic: str = Field(..., description="Market EPIC")
    confirm: bool = Field(default=False, description="Explicit confirmation")


# ============================================================
# WebSocket Streaming Models
# ============================================================


class PriceTick(BaseModel):
    """WebSocket price update."""

    epic: str = Field(..., description="Market EPIC")
    bid: float = Field(..., description="Bid price")
    offer: float = Field(..., description="Offer/ask price")
    timestamp: str = Field(..., description="Update timestamp (ISO 8601)")
    change_percent: float | None = Field(default=None, description="Price change percentage")


class StreamAlert(BaseModel):
    """Alert trigger event."""

    epic: str = Field(..., description="Market EPIC")
    condition: str = Field(..., description="Alert condition (LEVEL_ABOVE, LEVEL_BELOW, BREAKOUT)")
    trigger_price: float = Field(..., description="Price that triggered the alert")
    current_price: float = Field(..., description="Current market price")
    timestamp: str = Field(..., description="Alert timestamp (ISO 8601)")


class PortfolioSnapshot(BaseModel):
    """Real-time portfolio state."""

    positions: list[dict[str, Any]] = Field(..., description="List of open positions")
    total_pnl: float = Field(..., description="Total portfolio P&L")
    timestamp: str = Field(..., description="Snapshot timestamp (ISO 8601)")
