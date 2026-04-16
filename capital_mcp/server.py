"""MCP Server for Capital.com Open API - FastMCP Implementation."""

import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.resources import ResourceContent

from .capital_client import get_client
from .config import get_config
from .error_handler import ErrorHandlerMiddleware
from .models import (
    Direction,
    PreviewPositionRequest,
    PreviewWorkingOrderRequest,
    WorkingOrderType,
)
from .risk import get_risk_engine
from .session import get_session_manager
from .utils import poll_until

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Capital.com MCP Server")
mcp.add_middleware(ErrorHandlerMiddleware())


# ============================================================
# Session Tools
# ============================================================


@mcp.tool()
async def cap_session_status() -> dict[str, Any]:
    """
    Get current session status.

    Returns session info including login state, account ID, and token expiry estimate.
    No authentication required.
    """
    session = get_session_manager()
    status = session.get_status()
    return status.model_dump()


@mcp.tool()
async def cap_session_login(force: bool = False, account_id: str | None = None) -> dict[str, Any]:
    """
    Create a new session or verify existing session.

    Args:
        force: Force new login even if session is valid (default: false)
        account_id: Account ID to switch to after login (optional)

    Rate limit: 1 request/second (session limit).
    Creates CST and X-SECURITY-TOKEN for subsequent authenticated requests.
    """
    session = get_session_manager()
    data = await session.login(force=force, account_id=account_id)
    data["active_account_id"] = session.account_id
    return data


@mcp.tool()
async def cap_session_ping() -> dict[str, Any]:
    """
    Keep session alive.

    Extends session timeout by 10 minutes from last activity.
    Call periodically if doing long operations.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()
    data = await session.ping()
    return data


@mcp.tool()
async def cap_session_logout() -> dict[str, str]:
    """
    End session and clear authentication tokens.

    Requires authentication.
    """
    session = get_session_manager()
    await session.logout()
    return {"message": "Logged out successfully"}


# ============================================================
# Market Data Tools
# ============================================================


@mcp.tool()
async def cap_market_search(
    search_term: str | None = None, epics: list[str] | None = None, limit: int = 50
) -> dict[str, Any]:
    """
    Search for markets by term or EPICs.

    Args:
        search_term: Search term (e.g., "Bitcoin", "BTC") (optional)
        epics: List of EPICs to filter (optional)
        limit: Max results (default: 50, max: 1000)

    Returns list of matching markets with details.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    params: dict[str, Any] = {}
    if search_term:
        params["searchTerm"] = search_term
    if epics:
        params["epics"] = ",".join(epics)

    response = await client.get("/markets", params=params)
    data: dict[str, Any] = response.json()

    # Limit results
    if "markets" in data and len(data["markets"]) > limit:
        data["markets"] = data["markets"][:limit]

    return data


@mcp.tool()
async def cap_market_get(epic: str) -> dict[str, Any]:
    """
    Get detailed market information including dealing rules.

    Args:
        epic: Market EPIC (e.g., "SILVER", "BTCUSD")

    Returns market details, dealing rules (min/max size, increments), and current snapshot.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/markets/{epic}")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_market_navigation_root() -> dict[str, Any]:
    """
    Get root market navigation tree.

    Returns hierarchical market categories (e.g., Currencies, Indices, Commodities).
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/marketnavigation")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_market_navigation_node(node_id: str) -> dict[str, Any]:
    """
    Get market navigation node details.

    Args:
        node_id: Navigation node ID

    Returns child nodes and markets under this category.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/marketnavigation/{node_id}")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_market_prices(
    epic: str,
    resolution: str = "MINUTE_15",
    max: int = 200,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """
    Get historical price data (OHLC candles).

    Args:
        epic: Market EPIC
        resolution: Time resolution (MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK)
        max: Max candles to return (default: 200, max: 1000)
        from_date: Start date ISO 8601 (optional)
        to_date: End date ISO 8601 (optional)

    Returns historical price data with OHLC values.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    params: dict[str, Any] = {
        "resolution": resolution,
        "max": max,
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    response = await client.get(f"/prices/{epic}", params=params)
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_market_sentiment(market_id: str) -> dict[str, Any]:
    """
    Get client sentiment for a market.

    Args:
        market_id: Market ID (usually same as EPIC)

    Returns percentage of long vs short positions from other traders.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/clientsentiment/{market_id}")
    result: dict[str, Any] = response.json()
    return result


# ============================================================
# Account Tools
# ============================================================


@mcp.tool()
async def cap_account_list() -> dict[str, Any]:
    """
    List all trading accounts.

    Returns account details including balance, currency, and account type.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/accounts")
    data: dict[str, Any] = response.json()
    data["active_account_id"] = session.account_id
    return data


@mcp.tool()
async def cap_account_preferences_get() -> dict[str, Any]:
    """
    Get account preferences.

    Returns hedging mode setting and leverage configuration per asset class.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/accounts/preferences")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_account_preferences_set(
    hedging_mode: bool | None = None,
    leverages: dict[str, int | None] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Set account preferences (TRADE-GATED).

    Args:
        hedging_mode: Enable hedging mode (optional)
        leverages: Leverage per asset class - SHARES, CURRENCIES, INDICES, CRYPTOCURRENCIES, COMMODITIES (optional)
        confirm: Explicit confirmation required (default: false)

    IMPORTANT: This is a trade-gated operation.
    - Requires CAP_ALLOW_TRADING=true
    - Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true
    - Changes leverage and hedging mode affect risk exposure

    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    risk = get_risk_engine()
    risk.validate_execution_guards(confirm=confirm)

    # Build request body
    body: dict[str, Any] = {}
    if hedging_mode is not None:
        body["hedgingMode"] = hedging_mode
    if leverages is not None:
        body["leverages"] = leverages

    client = get_client()
    response = await client.put("/accounts/preferences", json=body)
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_account_history_activity(
    from_date: str | None = None, to_date: str | None = None, last_period: int = 600
) -> dict[str, Any]:
    """
    Get account activity history.

    Args:
        from_date: Start date ISO 8601 (optional)
        to_date: End date ISO 8601 (optional)
        last_period: Last N seconds (default: 600, max: 86400 for 1 day)

    Returns recent account activity including deals, orders, and updates.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    params: dict[str, Any] = {"lastPeriod": last_period}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    client = get_client()
    response = await client.get("/history/activity", params=params)
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_account_history_transactions(
    from_date: str | None = None,
    to_date: str | None = None,
    last_period: int = 600,
    type: str | None = None,
) -> dict[str, Any]:
    """
    Get transaction history.

    Args:
        from_date: Start date ISO 8601 (optional)
        to_date: End date ISO 8601 (optional)
        last_period: Last N seconds (default: 600)
        type: Transaction type filter (optional)

    Returns transaction history including deposits, withdrawals, and P&L.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    params: dict[str, Any] = {"lastPeriod": last_period}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    if type:
        params["type"] = type

    client = get_client()
    response = await client.get("/history/transactions", params=params)
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_account_demo_topup(amount: float, confirm: bool = False) -> dict[str, Any]:
    """
    Top up demo account balance (DEMO ONLY).

    Args:
        amount: Amount to add to balance
        confirm: Explicit confirmation required (default: false)

    IMPORTANT: Only works in DEMO environment (CAP_ENV=demo).
    Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true.
    Requires authentication.
    """
    config = get_config()

    # Demo-only check
    if config.cap_env.value != "demo":
        raise ValueError("Demo top-up only available in demo environment (CAP_ENV=demo)")

    # Confirmation check
    if config.cap_require_explicit_confirm and not confirm:
        raise ValueError("Explicit confirmation required. Set confirm=true")

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.post("/accounts/topUp", json={"amount": amount})
    result: dict[str, Any] = response.json()
    return result


# ============================================================
# Helper Functions
# ============================================================


async def _wait_for_confirmation(
    deal_reference: str, timeout_s: float = 15.0, poll_interval_ms: int = 500
) -> dict[str, Any]:
    """
    Helper function to wait for deal confirmation with polling.

    This is extracted so it can be called by both the tool and internal functions.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()

    async def check_confirm() -> dict[str, Any]:
        response = await client.get(f"/confirms/{deal_reference}")
        result: dict[str, Any] = response.json()
        return result

    def is_complete(data: dict[str, Any]) -> bool:
        status = data.get("status")
        return status in ("ACCEPTED", "REJECTED")

    result_data = await poll_until(
        check_confirm,
        is_complete,
        timeout_s=timeout_s,
        poll_interval_ms=poll_interval_ms,
    )

    if result_data is None:
        raise TimeoutError(f"Confirmation polling timed out after {timeout_s}s")

    result: dict[str, Any] = result_data
    return result


# ============================================================
# Trading Tools - Read-only
# ============================================================


@mcp.tool()
async def cap_trade_positions_list() -> dict[str, Any]:
    """
    List all open positions.

    Returns current positions with P&L, direction, size, and attached orders.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/positions")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_trade_positions_get(deal_id: str) -> dict[str, Any]:
    """
    Get position details by deal ID.

    Args:
        deal_id: Deal ID of the position

    Returns detailed position information.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/positions/{deal_id}")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_trade_orders_list() -> dict[str, Any]:
    """
    List all working orders.

    Returns pending LIMIT and STOP orders that haven't triggered yet.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/workingorders")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_trade_confirm_get(deal_reference: str) -> dict[str, Any]:
    """
    Get deal confirmation status.

    Args:
        deal_reference: Deal reference from trade operation (format: o_...)

    Returns confirmation status: ACCEPTED, REJECTED, or pending.
    Includes affected deal IDs if accepted.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/confirms/{deal_reference}")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_trade_confirm_wait(
    deal_reference: str, timeout_s: float = 15.0, poll_interval_ms: int = 500
) -> dict[str, Any]:
    """
    Wait for deal confirmation with polling.

    Args:
        deal_reference: Deal reference from trade operation
        timeout_s: Timeout in seconds (default: 15.0)
        poll_interval_ms: Poll interval in milliseconds (default: 500)

    Polls confirmation endpoint until ACCEPTED/REJECTED or timeout.
    Returns final confirmation status.
    Requires authentication.
    """
    return await _wait_for_confirmation(deal_reference, timeout_s, poll_interval_ms)


# ============================================================
# Trading Tools - Preview (Safe, No Side Effects)
# ============================================================


@mcp.tool()
async def cap_trade_preview_position(
    epic: str,
    direction: str,
    size: float,
    guaranteed_stop: bool = False,
    trailing_stop: bool = False,
    stop_level: float | None = None,
    stop_distance: float | None = None,
    stop_amount: float | None = None,
    profit_level: float | None = None,
    profit_distance: float | None = None,
    profit_amount: float | None = None,
) -> dict[str, Any]:
    """
    Preview a position before execution (NO SIDE EFFECTS).

    Args:
        epic: Market EPIC
        direction: BUY or SELL
        size: Position size
        guaranteed_stop: Use guaranteed stop (default: false)
        trailing_stop: Use trailing stop (default: false)
        stop_level: Stop loss price level (optional)
        stop_distance: Stop loss distance from entry (optional)
        stop_amount: Stop loss amount (optional)
        profit_level: Take profit price level (optional)
        profit_distance: Take profit distance from entry (optional)
        profit_amount: Take profit amount (optional)

    Validates against:
    - Trading enabled (CAP_ALLOW_TRADING)
    - Epic allowlist (CAP_ALLOWED_EPICS) - use 'ALL' to allow all instruments
    - Broker dealing rules (min/max size, increments)
    - Local risk policy (max position size)
    - Daily order limits

    Returns preview_id for use with cap_trade_execute_position.
    This is a READ-ONLY validation, no position is created.

    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    request = PreviewPositionRequest(
        epic=epic,
        direction=Direction(direction),
        size=size,
        guaranteed_stop=guaranteed_stop,
        trailing_stop=trailing_stop,
        stop_level=stop_level,
        stop_distance=stop_distance,
        stop_amount=stop_amount,
        profit_level=profit_level,
        profit_distance=profit_distance,
        profit_amount=profit_amount,
    )

    risk = get_risk_engine()
    preview = await risk.preview_position(request)

    return {
        "preview_id": preview.preview_id,
        "normalized_request": preview.normalized_request,
        "checks": [c.model_dump() for c in preview.checks],
        "all_checks_passed": preview.all_checks_passed,
        "estimated_entry": preview.estimated_entry,
        "estimated_risk_notes": preview.estimated_risk_notes,
        "expires_in_seconds": 120,
    }


@mcp.tool()
async def cap_trade_preview_working_order(
    epic: str,
    direction: str,
    type: str,
    level: float,
    size: float,
    guaranteed_stop: bool = False,
    trailing_stop: bool = False,
    stop_level: float | None = None,
    stop_distance: float | None = None,
    stop_amount: float | None = None,
    profit_level: float | None = None,
    profit_distance: float | None = None,
    profit_amount: float | None = None,
    good_till_date: str | None = None,
) -> dict[str, Any]:
    """
    Preview a working order before execution (NO SIDE EFFECTS).

    Args:
        epic: Market EPIC
        direction: BUY or SELL
        type: LIMIT or STOP
        level: Order trigger price level
        size: Order size
        guaranteed_stop: Use guaranteed stop (default: false)
        trailing_stop: Use trailing stop (default: false)
        stop_level: Stop loss price level (optional)
        stop_distance: Stop loss distance from entry (optional)
        stop_amount: Stop loss amount (optional)
        profit_level: Take profit price level (optional)
        profit_distance: Take profit distance from entry (optional)
        profit_amount: Take profit amount (optional)
        good_till_date: Expiry date ISO 8601 (optional)

    Similar validation to preview_position plus order-specific checks.
    Returns preview_id for use with cap_trade_execute_working_order.

    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    request = PreviewWorkingOrderRequest(
        epic=epic,
        direction=Direction(direction),
        type=WorkingOrderType(type),
        level=level,
        size=size,
        guaranteed_stop=guaranteed_stop,
        trailing_stop=trailing_stop,
        stop_level=stop_level,
        stop_distance=stop_distance,
        stop_amount=stop_amount,
        profit_level=profit_level,
        profit_distance=profit_distance,
        profit_amount=profit_amount,
        good_till_date=good_till_date,
    )

    risk = get_risk_engine()
    preview = await risk.preview_working_order(request)

    return {
        "preview_id": preview.preview_id,
        "normalized_request": preview.normalized_request,
        "checks": [c.model_dump() for c in preview.checks],
        "all_checks_passed": preview.all_checks_passed,
        "estimated_entry": preview.estimated_entry,
        "estimated_risk_notes": preview.estimated_risk_notes,
        "expires_in_seconds": 120,
    }


# ============================================================
# Trading Tools - Execute (Side Effects, Heavily Guarded)
# ============================================================


@mcp.tool()
async def cap_trade_execute_position(
    preview_id: str, confirm: bool = False, wait_for_confirm: bool = True, timeout_s: float = 15.0
) -> dict[str, Any]:
    """
    Execute a position (SIDE EFFECT - CREATES REAL TRADE).

    Args:
        preview_id: Preview ID from cap_trade_preview_position
        confirm: Explicit confirmation (default: false)
        wait_for_confirm: Wait for broker confirmation (default: true)
        timeout_s: Confirmation timeout (default: 15.0)

    CRITICAL SAFETY CHECKS:
    - Requires CAP_ALLOW_TRADING=true
    - Refuses if CAP_DRY_RUN=true
    - Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true
    - Preview must exist and all checks must have passed
    - Re-validates epic is still allowed (or 'ALL' is set)

    On success:
    - Creates position on broker
    - Returns deal_reference
    - Optionally waits for confirmation (ACCEPTED/REJECTED)
    - Increments daily order counter

    Rate limit: 1 request per 0.1 seconds (trading limit).
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    risk = get_risk_engine()
    risk.validate_execution_guards(confirm=confirm, preview_id=preview_id)

    preview = risk.get_preview(preview_id)
    normalized = preview.normalized_request

    # Build broker request
    broker_request: dict[str, Any] = {
        "epic": normalized["epic"],
        "direction": normalized["direction"],
        "size": normalized["size"],
    }

    # Add optional fields
    if normalized.get("guaranteed_stop"):
        broker_request["guaranteedStop"] = True
    if normalized.get("trailing_stop"):
        broker_request["trailingStop"] = True
    if normalized.get("stop_level"):
        broker_request["stopLevel"] = normalized["stop_level"]
    if normalized.get("stop_distance"):
        broker_request["stopDistance"] = normalized["stop_distance"]
    if normalized.get("stop_amount"):
        broker_request["stopAmount"] = normalized["stop_amount"]
    if normalized.get("profit_level"):
        broker_request["profitLevel"] = normalized["profit_level"]
    if normalized.get("profit_distance"):
        broker_request["profitDistance"] = normalized["profit_distance"]
    if normalized.get("profit_amount"):
        broker_request["profitAmount"] = normalized["profit_amount"]

    # Execute trade
    client = get_client()
    response = await client.post("/positions", json=broker_request, rate_limit_type="trading")
    data: dict[str, Any] = response.json()

    # Consume preview to prevent double execution
    risk.consume_preview(preview_id)

    # Increment order counter
    risk.increment_order_count()

    # Wait for confirmation if requested
    if wait_for_confirm and "dealReference" in data:
        try:
            confirm_data = await _wait_for_confirmation(
                deal_reference=data["dealReference"],
                timeout_s=timeout_s,
            )
            data["confirmation"] = confirm_data
        except TimeoutError:
            data["confirmation"] = {"status": "TIMEOUT", "message": "Confirmation timed out"}

    data["active_account_id"] = session.account_id
    return data


@mcp.tool()
async def cap_trade_execute_working_order(
    preview_id: str, confirm: bool = False, wait_for_confirm: bool = True, timeout_s: float = 15.0
) -> dict[str, Any]:
    """
    Execute a working order (SIDE EFFECT - CREATES REAL ORDER).

    Args:
        preview_id: Preview ID from cap_trade_preview_working_order
        confirm: Explicit confirmation (default: false)
        wait_for_confirm: Wait for broker confirmation (default: true)
        timeout_s: Confirmation timeout (default: 15.0)

    Same safety checks as execute_position.
    Creates a pending LIMIT or STOP order.

    Rate limit: 1 request per 0.1 seconds (trading limit).
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    risk = get_risk_engine()
    risk.validate_execution_guards(confirm=confirm, preview_id=preview_id)

    preview = risk.get_preview(preview_id)
    normalized = preview.normalized_request

    # Build broker request
    broker_request: dict[str, Any] = {
        "epic": normalized["epic"],
        "direction": normalized["direction"],
        "type": normalized["type"],
        "level": normalized["level"],
        "size": normalized["size"],
    }

    # Add optional fields
    if normalized.get("guaranteed_stop"):
        broker_request["guaranteedStop"] = True
    if normalized.get("trailing_stop"):
        broker_request["trailingStop"] = True
    if normalized.get("stop_level"):
        broker_request["stopLevel"] = normalized["stop_level"]
    if normalized.get("stop_distance"):
        broker_request["stopDistance"] = normalized["stop_distance"]
    if normalized.get("stop_amount"):
        broker_request["stopAmount"] = normalized["stop_amount"]
    if normalized.get("profit_level"):
        broker_request["profitLevel"] = normalized["profit_level"]
    if normalized.get("profit_distance"):
        broker_request["profitDistance"] = normalized["profit_distance"]
    if normalized.get("profit_amount"):
        broker_request["profitAmount"] = normalized["profit_amount"]
    if normalized.get("good_till_date"):
        broker_request["goodTillDate"] = normalized["good_till_date"]

    # Execute order
    client = get_client()
    response = await client.post("/workingorders", json=broker_request, rate_limit_type="trading")
    data: dict[str, Any] = response.json()

    # Consume preview to prevent double execution
    risk.consume_preview(preview_id)

    # Increment order counter
    risk.increment_order_count()

    # Wait for confirmation if requested
    if wait_for_confirm and "dealReference" in data:
        try:
            confirm_data = await _wait_for_confirmation(
                deal_reference=data["dealReference"],
                timeout_s=timeout_s,
            )
            data["confirmation"] = confirm_data
        except TimeoutError:
            data["confirmation"] = {"status": "TIMEOUT", "message": "Confirmation timed out"}

    data["active_account_id"] = session.account_id
    return data


@mcp.tool()
async def cap_trade_positions_close(
    deal_id: str, confirm: bool = False, wait_for_confirm: bool = True, timeout_s: float = 15.0
) -> dict[str, Any]:
    """
    Close an open position (SIDE EFFECT - CLOSES TRADE).

    Args:
        deal_id: Deal ID of position to close
        confirm: Explicit confirmation (default: false)
        wait_for_confirm: Wait for broker confirmation (default: true)
        timeout_s: Confirmation timeout (default: 15.0)

    CRITICAL: Requires CAP_ALLOW_TRADING=true and confirmation.
    Refuses if CAP_DRY_RUN=true.

    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    risk = get_risk_engine()
    risk.validate_execution_guards(confirm=confirm)

    client = get_client()
    response = await client.delete(f"/positions/{deal_id}")
    data: dict[str, Any] = response.json()

    # Wait for confirmation if requested
    if wait_for_confirm and "dealReference" in data:
        try:
            confirm_data = await _wait_for_confirmation(
                deal_reference=data["dealReference"],
                timeout_s=timeout_s,
            )
            data["confirmation"] = confirm_data
        except TimeoutError:
            data["confirmation"] = {"status": "TIMEOUT", "message": "Confirmation timed out"}

    data["active_account_id"] = session.account_id
    return data


@mcp.tool()
async def cap_trade_orders_cancel(
    deal_id: str, confirm: bool = False, wait_for_confirm: bool = True, timeout_s: float = 15.0
) -> dict[str, Any]:
    """
    Cancel a working order (SIDE EFFECT - CANCELS ORDER).

    Args:
        deal_id: Deal ID of order to cancel
        confirm: Explicit confirmation (default: false)
        wait_for_confirm: Wait for broker confirmation (default: true)
        timeout_s: Confirmation timeout (default: 15.0)

    CRITICAL: Requires CAP_ALLOW_TRADING=true and confirmation.
    Refuses if CAP_DRY_RUN=true.

    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    risk = get_risk_engine()
    risk.validate_execution_guards(confirm=confirm)

    client = get_client()
    response = await client.delete(f"/workingorders/{deal_id}")
    data: dict[str, Any] = response.json()

    # Wait for confirmation if requested
    if wait_for_confirm and "dealReference" in data:
        try:
            confirm_data = await _wait_for_confirmation(
                deal_reference=data["dealReference"],
                timeout_s=timeout_s,
            )
            data["confirmation"] = confirm_data
        except TimeoutError:
            data["confirmation"] = {"status": "TIMEOUT", "message": "Confirmation timed out"}

    data["active_account_id"] = session.account_id
    return data


# ============================================================
# Watchlist Tools
# ============================================================


@mcp.tool()
async def cap_watchlists_list() -> dict[str, Any]:
    """
    List all watchlists.

    Returns user's watchlists with IDs and names.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get("/watchlists")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_watchlists_get(watchlist_id: str) -> dict[str, Any]:
    """
    Get watchlist details including markets.

    Args:
        watchlist_id: Watchlist ID

    Returns watchlist with list of EPICs.
    Requires authentication.
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.get(f"/watchlists/{watchlist_id}")
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_watchlists_create(name: str, confirm: bool = False) -> dict[str, Any]:
    """
    Create a new watchlist.

    Args:
        name: Watchlist name (1-100 characters)
        confirm: Explicit confirmation (default: false)

    Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true.
    Requires authentication.
    """
    config = get_config()
    if config.cap_require_explicit_confirm and not confirm:
        raise ValueError("Explicit confirmation required. Set confirm=true")

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.post("/watchlists", json={"name": name})
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_watchlists_add_market(
    watchlist_id: str, epic: str, confirm: bool = False
) -> dict[str, Any]:
    """
    Add market to watchlist.

    Args:
        watchlist_id: Watchlist ID
        epic: Market EPIC to add
        confirm: Explicit confirmation (default: false)

    Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true.
    Requires authentication.
    """
    config = get_config()
    if config.cap_require_explicit_confirm and not confirm:
        raise ValueError("Explicit confirmation required. Set confirm=true")

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.put(f"/watchlists/{watchlist_id}", json={"epic": epic})
    result: dict[str, Any] = response.json()
    return result


@mcp.tool()
async def cap_watchlists_delete(watchlist_id: str, confirm: bool = False) -> dict[str, Any]:
    """
    Delete a watchlist.

    Args:
        watchlist_id: Watchlist ID
        confirm: Explicit confirmation (default: false)

    Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true.
    Requires authentication.
    """
    config = get_config()
    if config.cap_require_explicit_confirm and not confirm:
        raise ValueError("Explicit confirmation required. Set confirm=true")

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.delete(f"/watchlists/{watchlist_id}")
    return response.json() if response.text else {"status": "deleted"}


@mcp.tool()
async def cap_watchlists_remove_market(
    watchlist_id: str, epic: str, confirm: bool = False
) -> dict[str, Any]:
    """
    Remove market from watchlist.

    Args:
        watchlist_id: Watchlist ID
        epic: Market EPIC to remove
        confirm: Explicit confirmation (default: false)

    Requires confirm=true if CAP_REQUIRE_EXPLICIT_CONFIRM=true.
    Requires authentication.
    """
    config = get_config()
    if config.cap_require_explicit_confirm and not confirm:
        raise ValueError("Explicit confirmation required. Set confirm=true")

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()
    response = await client.delete(f"/watchlists/{watchlist_id}/{epic}")
    return response.json() if response.text else {"status": "removed"}


# ============================================================
# WebSocket Streaming Tools
# ============================================================


@mcp.tool()
async def cap_stream_prices(
    epics: list[str], duration_s: float = 300.0, update_interval_s: float = 1.0
) -> dict[str, Any]:
    """
    Stream real-time price updates for markets (WebSocket).

    Args:
        epics: List of market EPICs to monitor (max 40)
        duration_s: Stream duration in seconds (default: 300 = 5 minutes)
        update_interval_s: Minimum interval between updates (default: 1 second)

    Streams live bid/offer prices for specified markets. Updates are yielded
    as they arrive from Capital.com's WebSocket API.

    Note: Requires CAP_WS_ENABLED=true in configuration.
    Automatically reconnects on connection loss (up to 3 attempts).

    Returns streaming price ticks with bid, offer, timestamp, and change %.
    Connection auto-closes after duration_s seconds.

    Requires authentication.
    """
    from datetime import datetime

    from .websocket_client import get_websocket_client

    session = get_session_manager()
    await session.ensure_logged_in()

    # Validate EPIC count
    if len(epics) > 40:
        return {
            "error": "Too many EPICs",
            "message": f"Capital.com allows max 40 concurrent subscriptions (requested: {len(epics)})",
            "max_allowed": 40,
        }

    if not epics:
        return {
            "error": "No EPICs provided",
            "message": "Please specify at least one market EPIC to monitor",
        }

    # Stream prices
    ticks_collected = []
    last_update = datetime.utcnow()

    try:
        async with get_websocket_client() as ws:
            await ws.subscribe(epics)

            async for tick in ws.stream(duration=duration_s):
                # Throttle updates based on interval
                now = datetime.utcnow()
                if (now - last_update).total_seconds() >= update_interval_s:
                    ticks_collected.append(tick.model_dump())
                    last_update = now

        return {
            "status": "completed",
            "epics_monitored": epics,
            "duration_s": duration_s,
            "ticks_received": len(ticks_collected),
            "ticks": ticks_collected[-100:],  # Last 100 ticks to avoid huge responses
            "note": f"Streamed for {duration_s}s, collected {len(ticks_collected)} price updates",
        }

    except Exception as e:
        return {
            "error": "Streaming failed",
            "message": str(e),
            "ticks_before_error": len(ticks_collected),
        }


@mcp.tool()
async def cap_stream_alerts(
    alerts: dict[str, Any], duration_s: float = 300.0, auto_close: bool = False
) -> dict[str, Any]:
    """
    Monitor markets for alert conditions (WebSocket streaming).

    Args:
        alerts: Alert configuration per EPIC
                Format: {"EPIC": {"level": float, "direction": "ABOVE"|"BELOW"}}
                Example: {"GOLD": {"level": 2050.0, "direction": "ABOVE"}}
        duration_s: Maximum monitoring duration (default: 300 = 5 minutes)
        auto_close: Stop after first alert? (default: false)

    Monitors markets in real-time and triggers alerts when price conditions are met.
    Uses WebSocket streaming for instant notifications.

    Supported alert types:
    - ABOVE: Alert when price goes above level
    - BELOW: Alert when price goes below level

    Note: Requires CAP_WS_ENABLED=true in configuration.

    Returns list of triggered alerts with timestamp and prices.

    Requires authentication.
    """
    from .models import StreamAlert
    from .websocket_client import get_websocket_client

    session = get_session_manager()
    await session.ensure_logged_in()

    # Validate alerts
    if not alerts:
        return {
            "error": "No alerts configured",
            "message": "Please specify at least one alert condition",
        }

    epics = list(alerts.keys())
    if len(epics) > 40:
        return {
            "error": "Too many alerts",
            "message": f"Max 40 concurrent alerts (requested: {len(epics)})",
        }

    # Track triggered alerts
    triggered_alerts: list[StreamAlert] = []
    triggered_epics = set()

    try:
        async with get_websocket_client() as ws:
            await ws.subscribe(epics)

            async for tick in ws.stream(duration=duration_s):
                # Skip if already triggered and auto_close is enabled
                if auto_close and tick.epic in triggered_epics:
                    continue

                # Check alert condition
                alert_config = alerts.get(tick.epic)
                if not alert_config:
                    continue

                level = float(alert_config["level"])
                direction = alert_config["direction"].upper()
                mid_price = (tick.bid + tick.offer) / 2

                triggered = False
                condition = ""

                if direction == "ABOVE" and mid_price >= level:
                    triggered = True
                    condition = "LEVEL_ABOVE"
                elif direction == "BELOW" and mid_price <= level:
                    triggered = True
                    condition = "LEVEL_BELOW"

                if triggered:
                    alert = StreamAlert(
                        epic=tick.epic,
                        condition=condition,
                        trigger_price=level,
                        current_price=mid_price,
                        timestamp=tick.timestamp,
                    )
                    triggered_alerts.append(alert)
                    triggered_epics.add(tick.epic)

                    # Stop if auto_close and all alerts triggered
                    if auto_close and len(triggered_epics) == len(epics):
                        break

        return {
            "status": "completed",
            "alerts_configured": len(alerts),
            "alerts_triggered": len(triggered_alerts),
            "triggered_alerts": [alert.model_dump() for alert in triggered_alerts],
            "auto_close": auto_close,
        }

    except Exception as e:
        return {
            "error": "Alert monitoring failed",
            "message": str(e),
            "alerts_triggered_before_error": len(triggered_alerts),
            "triggered_alerts": [alert.model_dump() for alert in triggered_alerts],
        }


@mcp.tool()
async def cap_stream_portfolio(
    duration_s: float = 300.0, update_interval_s: float = 5.0
) -> dict[str, Any]:
    """
    Stream real-time portfolio P&L updates (WebSocket).

    Args:
        duration_s: Stream duration in seconds (default: 300 = 5 minutes)
        update_interval_s: Update frequency in seconds (default: 5 seconds)

    Fetches current open positions, subscribes to price updates for those markets,
    and calculates live P&L as prices change in real-time.

    Shows position-by-position P&L and total portfolio value, updating every
    update_interval_s seconds.

    Note: Requires CAP_WS_ENABLED=true in configuration.

    Returns portfolio snapshots with positions and total P&L.

    Requires authentication.
    """
    from datetime import datetime

    from .models import PortfolioSnapshot
    from .websocket_client import get_websocket_client

    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()

    # Fetch current positions
    try:
        positions_response = await client.get("/positions")
        positions_data = positions_response.json()
        positions = positions_data.get("positions", [])

        if not positions:
            return {
                "status": "no_positions",
                "message": "No open positions to monitor",
                "positions": [],
            }

        # Extract EPICs and position data from nested structure
        # API returns: [{"position": {...}, "market": {...}}, ...]
        epics = []
        initial_pnl: dict[str, float] = {}
        for pos in positions:
            market = pos.get("market", {})
            position = pos.get("position", {})
            epic = market.get("epic")
            if epic:
                epics.append(epic)
            deal_id = position.get("dealId")
            if deal_id:
                initial_pnl[deal_id] = float(position.get("upl", 0.0))

        if not epics:
            return {
                "status": "no_epics",
                "message": "Could not extract EPICs from open positions",
                "positions": [],
            }

        snapshots: list[PortfolioSnapshot] = []
        last_update = datetime.utcnow()

        async with get_websocket_client() as ws:
            await ws.subscribe(epics)

            async for _tick in ws.stream(duration=duration_s):
                # Throttle updates
                now = datetime.utcnow()
                if (now - last_update).total_seconds() < update_interval_s:
                    continue

                last_update = now

                total_pnl = 0.0
                updated_positions = []

                for pos in positions:
                    market = pos.get("market", {})
                    position = pos.get("position", {})
                    deal_id = position.get("dealId")
                    epic = market.get("epic")
                    pnl = float(position.get("upl", 0.0))
                    total_pnl += pnl

                    updated_positions.append(
                        {
                            "deal_id": deal_id,
                            "epic": epic,
                            "pnl": pnl,
                            "direction": position.get("direction"),
                            "size": position.get("size"),
                        }
                    )

                snapshot = PortfolioSnapshot(
                    positions=updated_positions,
                    total_pnl=total_pnl,
                    timestamp=now.isoformat() + "Z",
                )
                snapshots.append(snapshot)

        return {
            "status": "completed",
            "duration_s": duration_s,
            "positions_monitored": len(positions),
            "snapshots_collected": len(snapshots),
            "snapshots": [s.model_dump() for s in snapshots[-20:]],  # Last 20 snapshots
            "final_total_pnl": snapshots[-1].total_pnl if snapshots else 0.0,
        }

    except Exception as e:
        return {"error": "Portfolio streaming failed", "message": str(e)}


# ============================================================
# MCP Prompts (Workflow Templates)
# ============================================================


@mcp.prompt()
async def market_scan(
    watchlist_id: str = "", timeframe: str = "HOUR", lookback_periods: int = 24
) -> list[dict[str, Any]]:
    """
    Market scan workflow - Analyze markets in a watchlist.

    This prompt guides you through scanning markets for trading opportunities.
    It fetches a watchlist, retrieves price data for each market, and prompts
    you to analyze the data for patterns and opportunities.

    Args:
        watchlist_id: ID of watchlist to scan (leave empty to list all watchlists first)
        timeframe: Price resolution (MINUTE, MINUTE_5, HOUR, DAY) - default: HOUR
        lookback_periods: Number of candles to fetch (1-1000) - default: 24

    Workflow:
    1. If watchlist_id is empty, first call cap_watchlists_list to choose one
    2. Call cap_watchlists_get to get markets in the watchlist
    3. For each market, call cap_market_prices to get historical data
    4. Analyze the price data for trading opportunities
    5. Optionally check cap_market_sentiment for client positioning

    Example usage:
    - "Scan my watchlist for trading setups"
    - "Analyze markets in watchlist abc123 over the last day"
    """
    if not watchlist_id:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "# Market Scan Workflow\n\n"
                        "Let's scan your watchlist for trading opportunities.\n\n"
                        "**Step 1: Select Watchlist**\n"
                        "First, let's get your watchlists. Call the `cap_watchlists_list` tool "
                        "to see all available watchlists, then provide the watchlist ID you want to scan.\n\n"
                        "**Parameters for next steps:**\n"
                        f"- Timeframe: {timeframe}\n"
                        f"- Lookback periods: {lookback_periods}\n\n"
                        "After you have a watchlist ID, use this prompt again with the watchlist_id parameter."
                    ),
                },
            }
        ]

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# Market Scan Workflow\n\n"
                    f"Scanning watchlist: **{watchlist_id}**\n"
                    f"Timeframe: **{timeframe}** | Lookback: **{lookback_periods} periods**\n\n"
                    "**Step 2: Get Watchlist Markets**\n"
                    f"Call `cap_watchlists_get` with watchlist_id='{watchlist_id}' "
                    "to get the list of markets.\n\n"
                    "**Step 3: Fetch Price Data**\n"
                    "For each market (EPIC) in the watchlist:\n"
                    f"- Call `cap_market_prices` with resolution='{timeframe}' and max={lookback_periods}\n"
                    "- Collect OHLC data for analysis\n\n"
                    "**Step 4: Technical Analysis**\n"
                    "Analyze the price data for each market:\n"
                    "- Identify trends (uptrend, downtrend, ranging)\n"
                    "- Check for support/resistance levels\n"
                    "- Look for chart patterns (breakouts, reversals)\n"
                    "- Calculate key metrics (volatility, momentum)\n\n"
                    "**Step 5: Sentiment Check (Optional)**\n"
                    "For interesting markets, call `cap_market_sentiment` to see "
                    "how other clients are positioned (long vs short %).\n\n"
                    "**Output Format:**\n"
                    "Provide a summary table with:\n"
                    "- Market name & EPIC\n"
                    "- Current price & trend direction\n"
                    "- Key levels (support/resistance)\n"
                    "- Trading opportunity rating (Low/Medium/High)\n"
                    "- Brief rationale\n\n"
                    "Focus on actionable insights and clear opportunity identification."
                ),
            },
        }
    ]


@mcp.prompt()
async def trade_proposal(
    epic: str, direction: str = "BUY", thesis: str = "", risk_percent: float = 1.0
) -> list[dict[str, Any]]:
    """
    Trade proposal workflow - Design a trade with proper risk management.

    This prompt guides you through creating a trade proposal with entry,
    stop loss, and take profit levels. It uses preview to validate the trade
    WITHOUT executing it.

    Args:
        epic: Market EPIC to trade (e.g., SILVER, GOLD, BTCUSD)
        direction: Trade direction (BUY or SELL) - default: BUY
        thesis: Your trading thesis/reasoning
        risk_percent: Risk as % of account balance (default: 1.0%)

    Workflow:
    1. Call cap_market_get to fetch market details and dealing rules
    2. Calculate position size based on risk_percent and stop loss distance
    3. Call cap_trade_preview_position to validate the trade
    4. Return the preview_id for potential execution (DO NOT execute yet)

    Example usage:
    - "Propose a trade for SILVER"
    - "Create a trade proposal for buying GOLD with 2% risk"
    """
    direction_upper = direction.upper()
    if direction_upper not in ["BUY", "SELL"]:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"# Trade Proposal Error\n\n"
                        f"Invalid direction: '{direction}'. Must be 'BUY' or 'SELL'."
                    ),
                },
            }
        ]

    thesis_section = f"\n**Trading Thesis:**\n{thesis}\n" if thesis else ""

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# Trade Proposal Workflow\n\n"
                    f"**Market:** {epic}\n"
                    f"**Direction:** {direction_upper}\n"
                    f"**Risk:** {risk_percent}% of account balance\n"
                    f"{thesis_section}\n"
                    "---\n\n"
                    "**Step 1: Fetch Market Details**\n"
                    f"Call `cap_market_get` with epic='{epic}' to get:\n"
                    "- Current bid/offer prices\n"
                    "- Dealing rules (min/max size, increments)\n"
                    "- Market status (open/closed)\n"
                    "- Margin requirements\n\n"
                    "**Step 2: Calculate Position Size**\n"
                    "Based on your risk management:\n"
                    f"1. Account balance × {risk_percent}% = risk amount in currency\n"
                    "2. Determine stop loss distance (e.g., support/resistance level)\n"
                    "3. Position size = risk amount ÷ stop loss distance\n"
                    "4. Round size to market's minSizeIncrement\n"
                    "5. Ensure size is between minDealSize and maxDealSize\n\n"
                    "**Step 3: Define Stop Loss & Take Profit**\n"
                    "- **Stop Loss:** Technical level or fixed distance\n"
                    "  - For BUY: below current price (e.g., support level)\n"
                    "  - For SELL: above current price (e.g., resistance level)\n"
                    "- **Take Profit:** Risk/reward ratio (e.g., 2:1 or 3:1)\n"
                    "  - Target = Entry ± (Stop distance × reward ratio)\n\n"
                    "**Step 4: Preview the Trade**\n"
                    f"Call `cap_trade_preview_position` with:\n"
                    f"- epic: '{epic}'\n"
                    f"- direction: '{direction_upper}'\n"
                    "- size: calculated size\n"
                    "- stop_level: your stop loss price\n"
                    "- profit_level: your take profit price\n\n"
                    "**Step 5: Review Preview Results**\n"
                    "The preview will return:\n"
                    "- ✅ All risk checks (must pass)\n"
                    "- Estimated entry price\n"
                    "- Margin requirement\n"
                    "- Potential profit/loss at targets\n"
                    "- **preview_id** (save this for execution)\n\n"
                    "**Important Safety Notes:**\n"
                    "- This workflow does NOT execute the trade\n"
                    "- The preview_id is valid for 2 minutes\n"
                    "- Review all details before considering execution\n"
                    "- Use the 'execute_trade' prompt with the preview_id to execute\n\n"
                    "**Output Format:**\n"
                    "Present the trade proposal as:\n"
                    "```\n"
                    f"Market: {epic}\n"
                    f"Direction: {direction_upper}\n"
                    "Entry: [estimated price]\n"
                    "Stop Loss: [price] ([distance] points, [risk %]%)\n"
                    "Take Profit: [price] ([distance] points, [reward:risk ratio])\n"
                    "Position Size: [size] units\n"
                    "Margin Required: [amount]\n"
                    "Risk: [currency amount]\n"
                    "Potential Reward: [currency amount]\n"
                    "Preview ID: [uuid]\n"
                    "Risk Checks: [✅/❌ status]\n"
                    "```"
                ),
            },
        }
    ]


@mcp.prompt()
async def execute_trade(preview_id: str = "") -> list[dict[str, Any]]:
    """
    Execute trade workflow - Execute a previewed trade safely.

    This prompt guides you through executing a trade that was previously
    previewed. It includes confirmation polling and proper error handling.

    Args:
        preview_id: Preview ID from trade_proposal workflow (required)

    Workflow:
    1. Verify preview_id is provided
    2. Call cap_trade_execute_position with the preview_id and confirm=true
    3. Poll for confirmation using cap_trade_confirm_wait or cap_trade_confirm_get
    4. Report final status (ACCEPTED or REJECTED with reason)

    Safety notes:
    - Requires CAP_ALLOW_TRADING=true
    - Requires epic in CAP_ALLOWED_EPICS allowlist
    - Preview must not be expired (2-minute TTL)
    - This WILL place a real trade with the broker

    Example usage:
    - "Execute the previewed trade"
    - "Place the trade with preview ID abc-123-def"
    """
    if not preview_id:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "# Execute Trade Workflow - Missing Preview ID\n\n"
                        "⚠️ **Error:** preview_id is required.\n\n"
                        "**How to get a preview_id:**\n"
                        "1. Use the `trade_proposal` prompt to create a trade proposal\n"
                        "2. That workflow will call `cap_trade_preview_position`\n"
                        "3. The preview returns a preview_id (valid for 2 minutes)\n"
                        "4. Use that preview_id with this prompt to execute\n\n"
                        "**Example workflow:**\n"
                        "```\n"
                        "User: Propose a trade for SILVER\n"
                        "Assistant: [uses trade_proposal prompt, gets preview_id: 'abc-123']\n"
                        "User: Execute that trade\n"
                        "Assistant: [uses execute_trade prompt with preview_id='abc-123']\n"
                        "```"
                    ),
                },
            }
        ]

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# Execute Trade Workflow\n\n"
                    f"**Preview ID:** {preview_id}\n\n"
                    "⚠️ **DANGER: This workflow will place a REAL trade with the broker.**\n\n"
                    "**Pre-Execution Checklist:**\n"
                    "- [ ] Trading is enabled (CAP_ALLOW_TRADING=true)\n"
                    "- [ ] Market EPIC is in allowlist (CAP_ALLOWED_EPICS)\n"
                    "- [ ] Preview is not expired (generated < 2 minutes ago)\n"
                    "- [ ] Trade details were reviewed and approved by user\n"
                    "- [ ] Risk management is appropriate\n\n"
                    "**Step 1: Execute Position**\n"
                    f"Call `cap_trade_execute_position` with:\n"
                    f"- preview_id: '{preview_id}'\n"
                    "- confirm: true\n"
                    "- wait_for_confirm: true (recommended)\n\n"
                    "This will:\n"
                    "1. Validate the preview_id is still valid\n"
                    "2. Re-check all risk controls\n"
                    "3. Submit the order to Capital.com broker\n"
                    "4. Return a deal_reference\n"
                    "5. Automatically poll for confirmation (if wait_for_confirm=true)\n\n"
                    "**Step 2: Confirmation Status**\n"
                    "The broker will respond with:\n"
                    "- **ACCEPTED:** Trade executed successfully\n"
                    "  - deal_id: Position identifier\n"
                    "  - level: Actual fill price\n"
                    "  - size: Actual position size\n"
                    "  - direction: BUY or SELL\n"
                    "- **REJECTED:** Trade rejected by broker\n"
                    "  - reason: Why it was rejected (e.g., insufficient margin, market closed)\n\n"
                    "**Step 3: Post-Execution Actions**\n"
                    "If ACCEPTED:\n"
                    "- Call `cap_trade_positions_get` with the deal_id to see position details\n"
                    "- Verify stop loss and take profit were set correctly\n"
                    "- Record the trade in your trading journal\n\n"
                    "If REJECTED:\n"
                    "- Review the rejection reason\n"
                    "- Check account balance and margin\n"
                    "- Verify market is open\n"
                    "- Create a new preview if you want to try again\n\n"
                    "**Error Handling:**\n"
                    "Possible errors:\n"
                    "- `TRADING_DISABLED`: CAP_ALLOW_TRADING is false\n"
                    "- `EPIC_NOT_ALLOWED`: Market not in allowlist\n"
                    "- `PREVIEW_EXPIRED`: Preview is older than 2 minutes\n"
                    "- `PREVIEW_NOT_FOUND`: Invalid preview_id\n"
                    "- `UPSTREAM_ERROR`: Broker API error\n\n"
                    "**Output Format:**\n"
                    "Report execution result clearly:\n"
                    "```\n"
                    "✅ TRADE EXECUTED SUCCESSFULLY\n"
                    "Deal ID: [deal_id]\n"
                    "Market: [epic]\n"
                    "Direction: [BUY/SELL]\n"
                    "Size: [size] units\n"
                    "Entry Price: [level]\n"
                    "Stop Loss: [stop_level]\n"
                    "Take Profit: [profit_level]\n"
                    "Status: ACCEPTED\n"
                    "```\n\n"
                    "OR:\n\n"
                    "```\n"
                    "❌ TRADE REJECTED\n"
                    "Reason: [broker rejection reason]\n"
                    "Status: REJECTED\n"
                    "```"
                ),
            },
        }
    ]


@mcp.prompt()
async def position_review() -> list[dict[str, Any]]:
    """
    Position review workflow - Analyze current positions and orders.

    This prompt guides you through reviewing open positions and working orders,
    identifying exposures, and suggesting adjustments. It does NOT execute
    any trades - it's purely analytical.

    No arguments required - reviews all current positions and orders.

    Workflow:
    1. Call cap_trade_positions_list to get all open positions
    2. Call cap_trade_orders_list to get all working orders
    3. For each position, calculate P&L, risk, and exposure
    4. Identify correlations and concentration risks
    5. Suggest potential adjustments (WITHOUT executing them)

    Example usage:
    - "Review my current positions"
    - "Analyze my portfolio exposure"
    - "Show me my open trades and their status"
    """
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# Position Review Workflow\n\n"
                    "Let's analyze your current trading positions and orders.\n\n"
                    "**Step 1: Fetch Open Positions**\n"
                    "Call `cap_trade_positions_list` to get all open positions.\n\n"
                    "For each position, extract:\n"
                    "- deal_id & market (EPIC)\n"
                    "- Direction (BUY/SELL)\n"
                    "- Size & entry level (price)\n"
                    "- Current market price\n"
                    "- Unrealized P&L\n"
                    "- Stop loss & take profit levels\n\n"
                    "**Step 2: Fetch Working Orders**\n"
                    "Call `cap_trade_orders_list` to get all pending orders.\n\n"
                    "For each order, extract:\n"
                    "- order_id & market (EPIC)\n"
                    "- Direction (BUY/SELL)\n"
                    "- Size & trigger level\n"
                    "- Order type (LIMIT/STOP)\n"
                    "- Good till date\n\n"
                    "**Step 3: Calculate Key Metrics**\n\n"
                    "*Per Position:*\n"
                    "- P&L (currency and %)\n"
                    "- Risk (distance to stop loss in currency)\n"
                    "- Reward (distance to take profit in currency)\n"
                    "- Days held\n"
                    "- Status (winning/losing, at risk/safe)\n\n"
                    "*Portfolio Level:*\n"
                    "- Total unrealized P&L\n"
                    "- Total capital at risk (sum of all stop loss distances)\n"
                    "- Largest winning position\n"
                    "- Largest losing position\n"
                    "- Net directional exposure (net long/short across all positions)\n\n"
                    "**Step 4: Risk Analysis**\n\n"
                    "*Check for:*\n"
                    "- **Concentration Risk:** Too much exposure to one market\n"
                    "- **Correlation Risk:** Multiple positions in correlated markets\n"
                    "  - (e.g., GOLD and SILVER often move together)\n"
                    "- **Directional Bias:** Are you heavily long or short overall?\n"
                    "- **Stop Loss Coverage:** Are all positions protected?\n"
                    "- **Profit Target Coverage:** Do all positions have take profits?\n\n"
                    "**Step 5: Position Health Check**\n\n"
                    "For each position, assess:\n"
                    "- ✅ **Healthy:** In profit, stop loss at breakeven or better\n"
                    "- ⚠️ **At Risk:** Near stop loss, or stop too wide\n"
                    "- 🔍 **Needs Attention:** No stop loss, or profit target hit\n"
                    "- ❌ **Losing:** Underwater, stop loss not adjusted\n\n"
                    "**Step 6: Adjustment Suggestions**\n\n"
                    "*Potential actions (DO NOT execute):*\n"
                    "- Move stop loss to breakeven on winning positions\n"
                    "- Tighten stop loss if trade is going your way\n"
                    "- Close losing positions if thesis invalidated\n"
                    "- Take partial profits on large winners\n"
                    "- Cancel stale working orders\n"
                    "- Reduce exposure in correlated markets\n\n"
                    "**Step 7: Market Context (Optional)**\n\n"
                    "For key positions:\n"
                    "- Call `cap_market_sentiment` to see client positioning\n"
                    "- Call `cap_market_prices` to check recent price action\n"
                    "- Consider if stop loss is at a logical level\n\n"
                    "**Output Format:**\n\n"
                    "```\n"
                    "# Portfolio Summary\n"
                    "Total Open Positions: [count]\n"
                    "Total Working Orders: [count]\n"
                    "Total Unrealized P&L: [amount] ([%])\n"
                    "Capital at Risk: [amount]\n"
                    "Net Exposure: [net long/short description]\n\n"
                    "# Position Details\n\n"
                    "## Position 1: [EPIC] [BUY/SELL] [size]\n"
                    "Entry: [price] | Current: [price] | P&L: [amount] ([%])\n"
                    "Stop: [price] (Risk: [amount]) | Target: [price] (Reward: [amount])\n"
                    "Status: [✅/⚠️/🔍/❌] [description]\n"
                    "Suggestion: [specific action recommendation]\n\n"
                    "[... repeat for each position ...]\n\n"
                    "# Working Orders\n\n"
                    "## Order 1: [EPIC] [type] [direction] @ [trigger_price]\n"
                    "Size: [size] | Expires: [date]\n"
                    "Status: [active/stale]\n"
                    "Suggestion: [keep/cancel/adjust]\n\n"
                    "[... repeat for each order ...]\n\n"
                    "# Risk Assessment\n"
                    "Concentration: [assessment]\n"
                    "Correlation: [assessment]\n"
                    "Directional Bias: [assessment]\n"
                    "Stop Loss Coverage: [% of positions protected]\n\n"
                    "# Recommended Actions\n"
                    "1. [Priority action 1]\n"
                    "2. [Priority action 2]\n"
                    "3. [Priority action 3]\n"
                    "```\n\n"
                    "**Important Notes:**\n"
                    "- This workflow is READ-ONLY and analytical\n"
                    "- No trades will be executed automatically\n"
                    "- All suggestions require user approval before execution\n"
                    "- Use appropriate tools (cap_trade_positions_close, etc.) to act on suggestions"
                ),
            },
        }
    ]


# ============================================================
# MCP Resources (Read-Only Data)
# ============================================================


@mcp.resource("cap://status")
async def cap_status_resource() -> list[Any]:
    """
    Server status and session information.

    Provides current server health, session state, authentication status,
    and rate limit information. Useful for monitoring and debugging.
    """
    session = get_session_manager()
    status = session.get_status()

    config = get_config()
    allowed_epics = config.allowed_epics_list

    return [
        ResourceContent(
            {
                "server": {
                    "name": "Capital.com MCP Server",
                    "version": "0.1.0",
                    "trading_enabled": config.cap_allow_trading,
                },
                "session": {
                    "logged_in": status.logged_in,
                    "account_id": status.account_id,
                    "last_used_at": status.last_used_at,
                    "expires_in_s_estimate": status.expires_in_s_estimate,
                },
                "risk": {
                    "trading_enabled": config.cap_allow_trading,
                    "allowed_epics": allowed_epics,
                    "allowlist_mode": "ALL" if "ALL" in allowed_epics else "SPECIFIC",
                },
                "rate_limits": {
                    "requests_per_second": "10",
                    "note": "Capital.com enforces 10 req/s limit",
                },
            }
        )
    ]


@mcp.resource("cap://risk-policy")
async def cap_risk_policy_resource() -> list[Any]:
    """
    Current risk management policy configuration.

    Shows all active risk controls, safety checks, and trading restrictions.
    Includes allowlist configuration, trading toggles, and validation rules.
    """
    config = get_config()
    risk = get_risk_engine()

    allowed_epics = risk.get_allowed_epics()

    return [
        ResourceContent(
            {
                "trading_enabled": config.cap_allow_trading,
                "two_phase_execution": True,
                "description": "All trades require preview → explicit execution",
                "allowlist": {
                    "mode": "ALL" if "ALL" in allowed_epics else "SPECIFIC",
                    "epics": allowed_epics,
                    "note": "Only markets on this list can be traded (ALL = wildcard)",
                },
                "validation_layers": [
                    "1. Trading enabled check (CAP_ALLOW_TRADING env var)",
                    "2. Epic allowlist check (must be in CAP_ALLOWED_EPICS)",
                    "3. Two-phase execution (preview before execute)",
                    "4. Order size validation (non-zero, non-negative)",
                    "5. Stop/limit distance validation (positive)",
                    "6. Direction validation (BUY/SELL only)",
                    "7. Session authentication check",
                    "8. Rate limit compliance (10 req/s broker limit)",
                    "9. Deal reference validation (execute must match preview)",
                    "10. Broker-side validation (final gateway)",
                ],
                "safety_features": {
                    "preview_required": True,
                    "deal_reference_matching": True,
                    "authentication_required": True,
                    "rate_limiting": True,
                    "input_validation": True,
                },
            }
        )
    ]


@mcp.resource("cap://allowed-epics")
async def cap_allowed_epics_resource() -> list[Any]:
    """
    Trading allowlist configuration.

    Lists all markets (epics) that are permitted for trading operations.
    If "ALL" is present, all markets are allowed (wildcard mode).
    """
    risk = get_risk_engine()
    config = get_config()

    epics = list(risk.get_allowed_epics())
    has_wildcard = "ALL" in epics

    return [
        ResourceContent(
            {
                "mode": "WILDCARD" if has_wildcard else "SPECIFIC",
                "allowed_epics": epics,
                "count": len(epics),
                "trading_enabled": config.cap_allow_trading,
                "description": (
                    "Wildcard mode: ALL markets allowed"
                    if has_wildcard
                    else f"Restricted mode: {len(epics)} specific markets allowed"
                ),
                "configuration": {
                    "env_var": "CAP_ALLOWED_EPICS",
                    "example": "CAP_ALLOWED_EPICS=GOLD,SILVER,BTCUSD",
                    "wildcard": "CAP_ALLOWED_EPICS=ALL (allows all markets)",
                },
            }
        )
    ]


@mcp.resource("cap://market-cache/{epic}")
async def cap_market_cache_resource(epic: str) -> list[ResourceContent]:
    """
    Cached market details for a specific epic.

    Returns detailed market information including trading hours, margins,
    sizes, and currency. This is a live fetch (no actual cache yet).

    Args:
        epic: Market identifier (e.g., "GOLD", "SILVER", "CS.D.EURUSD.TODAY.IP")
    """
    session = get_session_manager()
    await session.ensure_logged_in()

    client = get_client()

    # Fetch market details
    response = await client.get(f"/markets/{epic}")
    data = response.json()

    snapshot = data.get("snapshot", {})
    instrument = data.get("instrument", {})
    dealing_rules = instrument.get("dealingRules", {})

    return [
        ResourceContent(
            {
                "epic": epic,
                "instrument_name": instrument.get("name"),
                "instrument_type": instrument.get("type"),
                "currency": (
                    instrument.get("currencies", [{}])[0].get("code")
                    if instrument.get("currencies")
                    else None
                ),
                "snapshot": {
                    "market_status": snapshot.get("marketStatus"),
                    "bid": snapshot.get("bid"),
                    "offer": snapshot.get("offer"),
                    "update_time": snapshot.get("updateTime"),
                },
                "dealing": {
                    "min_size": dealing_rules.get("minDealSize", {}).get("value"),
                    "max_size": dealing_rules.get("maxDealSize", {}).get("value"),
                    "min_step": dealing_rules.get("minStepDistance", {}).get("value"),
                    "min_stop_distance": dealing_rules.get("minNormalStopOrLimitDistance", {}).get(
                        "value"
                    ),
                },
                "margin": {
                    "factor": instrument.get("margin"),
                    "unit": (
                        instrument.get("marginDepositBands", [{}])[0].get("unit")
                        if instrument.get("marginDepositBands")
                        else None
                    ),
                },
                "opening_hours": instrument.get("openingHours"),
                "cached_at": session.get_status().last_used_at,
            }
        )
    ]


@mcp.prompt()
async def live_price_monitor(
    epics: list[str] | None = None, duration_minutes: float = 5.0, threshold_percent: float = 1.0
) -> list[dict[str, Any]]:
    """
    Live price monitor - Real-time price tracking with movement alerts (WebSocket streaming).

    Monitor live market prices with instant alerts when prices move beyond threshold.
    Uses WebSocket streaming for real-time updates with sub-second latency.

    Args:
        epics: List of market EPICs to monitor (leave empty to search/select, max 40)
        duration_minutes: How long to monitor (default: 5 minutes, max: 10 minutes)
        threshold_percent: Alert when price moves > this % (default: 1.0%)

    Workflow:
    1. Select markets to monitor (or provide EPICs directly)
    2. Fetch initial prices to establish baseline
    3. [STREAM] Subscribe to real-time WebSocket price updates
    4. Display live price board with continuous updates
    5. Alert when any market moves > threshold_percent
    6. Auto-stop after duration_minutes

    Note: Requires CAP_WS_ENABLED=true in configuration.
    Capital.com WebSocket sessions last 10 minutes maximum.

    Example usage:
    - "Monitor GOLD and SILVER prices for 2 minutes"
    - "Watch BTC for next 5 minutes, alert on 2% moves"
    - "Track my watchlist in real-time"
    """
    if not epics:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "# 📊 Live Price Monitor Workflow\n\n"
                        "**Real-time price tracking with WebSocket streaming**\n\n"
                        "---\n\n"
                        "**Step 1: Select Markets**\n"
                        "First, choose which markets you want to monitor:\n"
                        "- Call `cap_market_search` to find markets by name/category\n"
                        "- Or call `cap_watchlists_list` to see your watchlists\n"
                        "- Or call `cap_watchlists_get` to get markets from a specific watchlist\n"
                        "- Maximum: 40 markets simultaneously\n\n"
                        "**Parameters for next steps:**\n"
                        f"- Duration: {duration_minutes} minutes\n"
                        f"- Alert threshold: {threshold_percent}% price movement\n\n"
                        "After you have your EPICs list, use this prompt again with the epics parameter.\n"
                        'Example: `live_price_monitor(epics=["GOLD", "SILVER"], duration_minutes=2.0)`'
                    ),
                },
            }
        ]

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# 📊 Live Price Monitor\n\n"
                    f"**Monitoring:** {', '.join(epics[:5])}"
                    + (f" (+{len(epics) - 5} more)" if len(epics) > 5 else "")
                    + "\n"
                    f"**Duration:** {duration_minutes} minutes | "
                    f"**Alert threshold:** {threshold_percent}%\n\n"
                    "---\n\n"
                    "**Step 2: Fetch Initial Prices**\n"
                    "Get baseline prices for comparison:\n"
                    "- For each EPIC, call `cap_market_prices` with resolution=MINUTE and max=1\n"
                    "- Record current bid/offer/mid prices\n"
                    "- This establishes the starting point for threshold alerts\n\n"
                    "**Step 3: [STREAM] Start Real-Time Monitoring**\n"
                    f"Call `cap_stream_prices` to start WebSocket streaming:\n"
                    f"- epics: {epics}\n"
                    f"- duration_s: {duration_minutes * 60}\n"
                    "- update_interval_s: 1.0 (updates every second)\n\n"
                    "⚡ **While streaming:**\n"
                    "- Display live price board (update continuously as ticks arrive)\n"
                    "- Calculate % change from baseline for each market\n"
                    f"- **Alert** when any market moves > {threshold_percent}%\n"
                    "- Show timestamp for each update\n\n"
                    "**Step 4: Present Live Dashboard**\n"
                    "Format the output as a continuously updating table:\n"
                    "```\n"
                    "📊 LIVE PRICES (auto-updating)\n"
                    "───────────────────────────────────────\n"
                    "EPIC     | Bid      | Offer    | Change\n"
                    "───────────────────────────────────────\n"
                    "GOLD     | 2,048.50 | 2,049.00 | +0.5% ⚡\n"
                    "SILVER   | 27.80    | 27.82    | -0.2%\n"
                    "───────────────────────────────────────\n"
                    "Last update: HH:MM:SS\n"
                    "```\n\n"
                    f"⚠️ **Alert format** (when change > {threshold_percent}%):\n"
                    "```\n"
                    "⚡ PRICE ALERT: GOLD\n"
                    f"   Moved {threshold_percent}%+ from baseline\n"
                    "   Current: $2,048.50 (was $2,038.00)\n"
                    "   Change: +$10.50 (+0.52%)\n"
                    "   Time: 14:32:18\n"
                    "```\n\n"
                    "**Important Notes:**\n"
                    "- ✅ WebSocket provides sub-second updates\n"
                    f"- ⏱️ Stream auto-stops after {duration_minutes} minutes\n"
                    "- 🔄 Auto-reconnects if connection drops (up to 3 attempts)\n"
                    "- 🚫 Requires CAP_WS_ENABLED=true in config\n"
                    "- 📊 Capital.com sends updates when prices change (not on fixed interval)\n"
                ),
            },
        }
    ]


@mcp.prompt()
async def real_time_alerts(
    alert_config: dict[str, float] | None = None,
    duration_minutes: float = 5.0,
    auto_stop: bool = True,
) -> list[dict[str, Any]]:
    """
    Real-time alerts - Conditional alerts for trading opportunities (WebSocket streaming).

    Set price level alerts and get instant notifications when markets hit your targets.
    Uses WebSocket for real-time monitoring with immediate alert triggers.

    Args:
        alert_config: Alert levels per EPIC (e.g., {"GOLD": 2050.0, "SILVER": 28.5})
        duration_minutes: Maximum monitoring duration (default: 5 minutes)
        auto_stop: Stop monitoring after first alert? (default: true)

    Workflow:
    1. Configure alert conditions (price levels for each market)
    2. [STREAM] Subscribe to WebSocket price updates
    3. Monitor continuously for alert triggers
    4. Emit instant alert when condition met
    5. Optionally continue monitoring or stop after first alert

    Note: Requires CAP_WS_ENABLED=true in configuration.

    Example usage:
    - "Alert me when GOLD reaches 2050"
    - "Notify when SILVER drops below 28"
    - "Watch breakout levels for BTC and ETH"
    """
    if not alert_config:
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "# ⚡ Real-Time Alerts Setup\n\n"
                        "**Instant notifications when markets hit your target levels**\n\n"
                        "---\n\n"
                        "**Step 1: Identify Target Markets & Levels**\n"
                        "Determine which markets you want to monitor and at what price levels:\n\n"
                        "1. **Find markets:**\n"
                        "   - Call `cap_market_search` to search by name\n"
                        "   - Call `cap_market_get` to check current prices\n\n"
                        "2. **Define alert levels:**\n"
                        "   - Support/resistance levels (technical analysis)\n"
                        "   - Psychological levels (round numbers)\n"
                        "   - Breakout points\n"
                        "   - Previous highs/lows\n\n"
                        "**Step 2: Configure Alert Parameters**\n"
                        "Decide:\n"
                        f"- **Duration:** How long to monitor (default: {duration_minutes} min, max: 10 min)\n"
                        f"- **Auto-stop:** Stop after first alert? (default: {auto_stop})\n\n"
                        "**Step 3: Format Alert Configuration**\n"
                        "Create alert_config dictionary:\n"
                        "```python\n"
                        "{\n"
                        '  "GOLD": 2050.0,    # Alert when GOLD hits 2050\n'
                        '  "SILVER": 28.5,    # Alert when SILVER hits 28.5\n'
                        '  "BTCUSD": 45000.0  # Alert when BTC hits 45000\n'
                        "}\n"
                        "```\n\n"
                        "Then call this prompt again with alert_config parameter.\n"
                        'Example: `real_time_alerts(alert_config={"GOLD": 2050.0}, duration_minutes=5.0)`'
                    ),
                },
            }
        ]

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# ⚡ Real-Time Alert Monitoring\n\n"
                    f"**Configured alerts:** {len(alert_config)} markets\n"
                    f"**Duration:** {duration_minutes} minutes | "
                    f"**Auto-stop after alert:** {'Yes' if auto_stop else 'No'}\n\n"
                    "---\n\n"
                    "**Alert Configuration:**\n"
                    + "\n".join(
                        [
                            f"- {epic}: {level:,.2f}"
                            for epic, level in list(alert_config.items())[:10]
                        ]
                    )
                    + ("\n- ..." if len(alert_config) > 10 else "")
                    + "\n\n"
                    "**Step 2: Fetch Current Prices**\n"
                    "Get current market prices to determine direction:\n"
                    "- For each EPIC in alert_config, call `cap_market_get`\n"
                    "- Check if current price is above or below alert level\n"
                    "- Determine alert direction (ABOVE if currently below, BELOW if currently above)\n\n"
                    "**Step 3: [STREAM] Start Alert Monitoring**\n"
                    "Call `cap_stream_alerts` with formatted configuration:\n"
                    "```python\n"
                    "alerts = {\n"
                    + "\n".join(
                        [
                            f'  "{epic}": {{"level": {level}, "direction": "ABOVE"}}  # Adjust direction based on current price'
                            for epic, level in list(alert_config.items())[:3]
                        ]
                    )
                    + "\n}\n"
                    "```\n\n"
                    f"- duration_s: {duration_minutes * 60}\n"
                    f"- auto_close: {auto_stop}\n\n"
                    "⚡ **While monitoring:**\n"
                    "- WebSocket streams live price updates\n"
                    "- Each tick is checked against alert conditions\n"
                    "- Instant notification when level crossed\n"
                    + (
                        "- Monitoring stops after first alert\n"
                        if auto_stop
                        else "- Continues monitoring all markets\n"
                    )
                    + "\n"
                    "**Step 4: Handle Alert Triggers**\n"
                    "When an alert fires, display:\n"
                    "```\n"
                    "🚨 ALERT TRIGGERED! 🚨\n"
                    "───────────────────────────────────────\n"
                    "Market: GOLD\n"
                    "Condition: Price ABOVE 2050.00\n"
                    "Trigger Price: 2050.00\n"
                    "Current Price: 2050.25\n"
                    "Timestamp: 2026-01-16T14:32:18Z\n"
                    "───────────────────────────────────────\n"
                    "```\n\n"
                    "**Optional Next Actions:**\n"
                    "After alert triggers:\n"
                    "1. ✅ Call `cap_market_get` to get full market details\n"
                    "2. ✅ Use `trade_proposal` prompt to design trade entry\n"
                    "3. ✅ Check `cap_market_sentiment` for positioning data\n"
                    "4. ✅ Review technical levels with `cap_market_prices`\n\n"
                    "**Important Notes:**\n"
                    "- ⚡ Alerts trigger within milliseconds of level breach\n"
                    "- 🔄 Auto-reconnects on WebSocket disconnection\n"
                    "- 📊 Checks mid-price: (bid + offer) / 2\n"
                    "- 🚫 Requires CAP_WS_ENABLED=true\n"
                    f"- ⏱️ Max duration: {duration_minutes} minutes (Capital.com limit: 10 min)\n"
                ),
            },
        }
    ]


@mcp.prompt()
async def live_portfolio_monitor(
    duration_minutes: float = 5.0, alert_pnl_threshold: float = 100.0
) -> list[dict[str, Any]]:
    """
    Live portfolio monitor - Real-time P&L tracking for open positions (WebSocket streaming).

    Watch your portfolio P&L update in real-time as market prices move.
    Get instant alerts when total P&L crosses thresholds.

    Args:
        duration_minutes: Monitoring duration (default: 5 minutes, max: 10 minutes)
        alert_pnl_threshold: Alert when total P&L exceeds this amount (default: $100)

    Workflow:
    1. Fetch current open positions
    2. [STREAM] Subscribe to price updates for position markets
    3. Calculate live P&L as prices change
    4. Display real-time portfolio dashboard
    5. Alert when P&L crosses threshold

    Note: Requires CAP_WS_ENABLED=true and active positions.

    Example usage:
    - "Monitor my portfolio P&L for 5 minutes"
    - "Watch positions in real-time, alert at $500 P&L"
    - "Track live portfolio performance"
    """
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "# 💼 Live Portfolio Monitor\n\n"
                    f"**Duration:** {duration_minutes} minutes | "
                    f"**P&L alert threshold:** ${alert_pnl_threshold:,.2f}\n\n"
                    "---\n\n"
                    "**Step 1: Fetch Open Positions**\n"
                    "Get your current portfolio:\n"
                    "- Call `cap_trade_positions_list` to get all open positions\n"
                    "- Extract: deal IDs, EPICs, directions, sizes, current P&L\n"
                    "- If no positions: Cannot monitor empty portfolio\n\n"
                    "**Step 2: Extract Position EPICs**\n"
                    "Identify which markets to monitor:\n"
                    "- Get unique EPICs from all positions\n"
                    "- Note: Max 40 markets (Capital.com WebSocket limit)\n"
                    "- If > 40 positions, prioritize largest positions\n\n"
                    "**Step 3: [STREAM] Monitor Portfolio in Real-Time**\n"
                    f"Call `cap_stream_portfolio`:\n"
                    f"- duration_s: {duration_minutes * 60}\n"
                    "- update_interval_s: 5.0 (updates every 5 seconds)\n\n"
                    "📊 **While streaming:**\n"
                    "- WebSocket streams price updates for all position markets\n"
                    "- Recalculates P&L every 5 seconds\n"
                    "- Displays live portfolio dashboard\n"
                    f"- **Alerts** when total P&L crosses ${alert_pnl_threshold:,.2f}\n\n"
                    "**Step 4: Display Live Dashboard**\n"
                    "Format as continuously updating portfolio summary:\n"
                    "```\n"
                    "💼 LIVE PORTFOLIO DASHBOARD\n"
                    "═══════════════════════════════════════════════════════\n"
                    "Position     | Direction | Size  | P&L       | Status\n"
                    "───────────────────────────────────────────────────────\n"
                    "GOLD         | BUY       | 0.5   | +$125.50  | ✅\n"
                    "SILVER       | SELL      | 2.0   | -$18.20   | 📊\n"
                    "BTCUSD       | BUY       | 0.1   | +$230.00  | ⚡\n"
                    "───────────────────────────────────────────────────────\n"
                    "TOTAL P&L:                         +$337.30  | 🎯\n"
                    "═══════════════════════════════════════════════════════\n"
                    "Last update: 14:32:18 | Updates every 5s\n"
                    "```\n\n"
                    "**Status Indicators:**\n"
                    "- ✅ Winning (P&L > 0)\n"
                    "- 📊 Flat (P&L ≈ 0)\n"
                    "- ⚠️ Losing but within risk tolerance\n"
                    "- 🔴 Significant loss\n\n"
                    f"**Alert Format** (when total P&L crosses ${alert_pnl_threshold:,.2f}):\n"
                    "```\n"
                    f"🎯 P&L THRESHOLD ALERT!\n"
                    f"   Total P&L crossed ${alert_pnl_threshold:,.2f}\n"
                    "   Current P&L: +$337.30\n"
                    "   Time: 14:32:18\n"
                    "   Action: Review positions, consider taking profits\n"
                    "```\n\n"
                    "**Optional Follow-Up Actions:**\n"
                    "Based on live P&L:\n"
                    "1. 💰 **Taking Profits:** Use `cap_trade_positions_close` to close winning positions\n"
                    "2. 🛑 **Cutting Losses:** Close losing positions before they worsen\n"
                    "3. 📊 **Position Details:** Call `cap_trade_positions_get` for specific position\n"
                    "4. 🎯 **Adjust Stops:** Update stop losses on running positions\n\n"
                    "**Important Notes:**\n"
                    "- ⚡ P&L updates as prices change (real-time)\n"
                    "- 🔄 Updates every 5 seconds (configurable)\n"
                    "- 📊 Includes all open positions automatically\n"
                    "- 🚫 Requires CAP_WS_ENABLED=true and active positions\n"
                    f"- ⏱️ Auto-stops after {duration_minutes} minutes\n"
                    "- 💡 Simplified P&L calculation (demo purposes - real calc needs more data)\n"
                ),
            },
        }
    ]


# ============================================================
# Server Lifecycle
# ============================================================


if __name__ == "__main__":
    config = get_config()
    logger.info(f"Starting Capital.com MCP Server (env: {config.cap_env.value})")
    logger.info(f"Trading enabled: {config.cap_allow_trading}")

    if config.cap_allow_trading:
        allowed = config.allowed_epics_list
        if allowed and allowed[0].upper() == "ALL":
            logger.info("Allowed EPICs: ALL (no restrictions)")
        else:
            logger.info(f"Allowed EPICs: {allowed}")

    # Run FastMCP server (handles STDIO automatically)
    mcp.run()
