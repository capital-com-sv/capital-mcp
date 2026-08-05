"""Risk engine and preview cache for trade validation."""

import logging
from datetime import datetime, timezone
from typing import Any

from .capital_client import get_client
from .config import get_config
from .errors import (
    ConfirmRequiredError,
    DryRunError,
    PreviewError,
    RiskLimitError,
    TradingDisabledError,
)
from .models import (
    Direction,
    PreviewPositionRequest,
    PreviewResult,
    PreviewWorkingOrderRequest,
    RiskCheck,
    UpdateWorkingOrderRequest,
)

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Risk engine for trade validation and preview caching.

    Implements:
    - Trading enable/disable checks
    - Epic allowlist validation
    - Size limit validation
    - Position/order count limits
    - Preview cache with TTL
    - Size normalization
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.client = get_client()

        # Preview cache: {preview_id: PreviewResult}
        self._preview_cache: dict[str, PreviewResult] = {}

        # Daily order counter (resets at midnight UTC)
        self._order_count: int = 0
        self._order_count_date: str | None = None

    def _check_daily_limit(self) -> RiskCheck:
        """Check if daily order limit is reached."""
        today = datetime.now(timezone.utc).date().isoformat()

        # Reset counter if new day
        if self._order_count_date != today:
            self._order_count = 0
            self._order_count_date = today

        if self._order_count >= self.config.cap_max_orders_per_day:
            return RiskCheck(
                check="daily_order_limit",
                passed=False,
                message=f"Daily order limit reached ({self.config.cap_max_orders_per_day})",
            )

        return RiskCheck(
            check="daily_order_limit",
            passed=True,
            message=f"Daily orders: {self._order_count}/{self.config.cap_max_orders_per_day}",
        )

    def get_allowed_epics(self) -> list[str]:
        """Get list of allowed epics from config."""
        return list(self.config.allowed_epics_list)

    def increment_order_count(self) -> None:
        """Increment daily order counter."""
        today = datetime.now(timezone.utc).date().isoformat()
        if self._order_count_date != today:
            self._order_count = 0
            self._order_count_date = today
        self._order_count += 1

    async def _get_market_details(self, epic: str) -> dict[str, Any]:
        """Fetch market details including dealing rules."""
        response = await self.client.get(f"/markets/{epic}")
        result: dict[str, Any] = response.json()
        return result

    def _normalize_size(
        self,
        size: float,
        min_size: float,
        max_size: float,
        increment: float,
    ) -> tuple[float, list[str]]:
        """
        Normalize position/order size to broker requirements.

        Returns:
            (normalized_size, warnings)
        """
        warnings: list[str] = []
        # Round to nearest increment
        normalized = round(size / increment) * increment

        if abs(normalized - size) > 0.0001:
            warnings.append(f"Size rounded from {size} to {normalized} (increment: {increment})")

        # Reject if outside broker dealing rules
        if normalized < min_size or normalized > max_size:
            raise RiskLimitError(
                f"Size {size} is outside the allowed range for this market. "
                f"Please choose a size between {min_size} and {max_size}."
            )

        return normalized, warnings

    async def preview_position(self, request: PreviewPositionRequest) -> PreviewResult:
        """
        Preview a position and validate against risk policy.

        Args:
            request: Position preview request

        Returns:
            Preview result with checks and normalized values
        """
        checks: list[RiskCheck] = []

        # Check 1: Trading enabled
        if not self.config.cap_allow_trading:
            checks.append(
                RiskCheck(
                    check="trading_enabled",
                    passed=False,
                    message="Trading is disabled (CAP_ALLOW_TRADING=false)",
                )
            )
            return PreviewResult(
                normalized_request={},
                checks=checks,
                all_checks_passed=False,
            )

        checks.append(RiskCheck(check="trading_enabled", passed=True, message="Trading is enabled"))

        # Check 2: Epic allowlist
        if not self.config.is_epic_allowed(request.epic):
            checks.append(
                RiskCheck(
                    check="epic_allowed",
                    passed=False,
                    message=f"Epic '{request.epic}' not in allowlist",
                )
            )
            return PreviewResult(
                normalized_request={},
                checks=checks,
                all_checks_passed=False,
            )

        # Normalize epic to uppercase for Capital.com API compatibility
        epic = request.epic.upper()

        checks.append(
            RiskCheck(check="epic_allowed", passed=True, message=f"Epic '{epic}' is allowed")
        )

        # Check 3: Daily order limit
        daily_check = self._check_daily_limit()
        checks.append(daily_check)

        if not daily_check.passed:
            return PreviewResult(
                normalized_request={},
                checks=checks,
                all_checks_passed=False,
            )

        # Fetch market details
        try:
            market_data = await self._get_market_details(epic)
        except Exception as e:
            logger.error(f"Failed to fetch market details for {epic}: {e}")
            checks.append(
                RiskCheck(
                    check="market_details",
                    passed=False,
                    message=f"Failed to fetch market details: {str(e)}",
                )
            )
            return PreviewResult(
                normalized_request={},
                checks=checks,
                all_checks_passed=False,
            )

        checks.append(
            RiskCheck(check="market_details", passed=True, message="Market details fetched")
        )

        # Extract dealing rules
        dealing_rules = market_data.get("dealingRules", {})
        min_deal_size = dealing_rules.get("minDealSize", {}).get("value", 0.1)
        max_deal_size = dealing_rules.get("maxDealSize", {}).get("value", 1000.0)
        min_size_increment = dealing_rules.get("minSizeIncrement", {}).get("value", 0.1)

        # Check 4: Normalize size
        normalized_size, size_warnings = self._normalize_size(
            request.size,
            min_deal_size,
            max_deal_size,
            min_size_increment,
        )

        # Check 5: Max position size policy
        if normalized_size > self.config.cap_max_position_size:
            checks.append(
                RiskCheck(
                    check="max_position_size",
                    passed=False,
                    message=f"Size {normalized_size} exceeds policy limit {self.config.cap_max_position_size}",
                )
            )
            return PreviewResult(
                normalized_request={},
                checks=checks,
                all_checks_passed=False,
            )

        checks.append(
            RiskCheck(
                check="max_position_size",
                passed=True,
                message=f"Size {normalized_size} within limit {self.config.cap_max_position_size}",
            )
        )

        # Build normalized request (mode='json' to serialize enums as strings)
        normalized_request = request.model_dump(mode="json")
        normalized_request["epic"] = epic
        normalized_request["size"] = normalized_size
        normalized_request["size_warnings"] = size_warnings

        # Extract snapshot for entry price estimate
        snapshot = market_data.get("snapshot", {})
        estimated_entry = None
        if request.direction == Direction.BUY:
            estimated_entry = snapshot.get("offer")
        else:
            estimated_entry = snapshot.get("bid")

        # Create preview result
        result = PreviewResult(
            normalized_request=normalized_request,
            checks=checks,
            all_checks_passed=all(c.passed for c in checks),
            estimated_entry=estimated_entry,
            estimated_risk_notes="Preview only; actual execution may differ based on market conditions.",
        )

        # Cache the preview
        self._preview_cache[result.preview_id] = result
        logger.info(f"Created preview {result.preview_id} for {epic}")

        return result

    async def preview_working_order(self, request: PreviewWorkingOrderRequest) -> PreviewResult:
        """Preview a working order (similar to position preview)."""
        # Convert to position request for validation (epic uppercased inside preview_position)
        position_request = PreviewPositionRequest(
            epic=request.epic,
            direction=request.direction,
            size=request.size,
            guaranteed_stop=request.guaranteed_stop,
            trailing_stop=request.trailing_stop,
            stop_level=request.stop_level,
            stop_distance=request.stop_distance,
            stop_amount=request.stop_amount,
            profit_level=request.profit_level,
            profit_distance=request.profit_distance,
            profit_amount=request.profit_amount,
        )

        # Run position checks
        result = await self.preview_position(position_request)

        # Add working order specific fields
        if result.all_checks_passed:
            result.normalized_request["type"] = request.type.value
            result.normalized_request["level"] = request.level
            if request.good_till_date:
                result.normalized_request["good_till_date"] = request.good_till_date

        return result

    async def _fetch_working_order(self, deal_id: str) -> dict[str, Any]:
        """Fetch a single working order by dealId from GET /workingorders.

        Returns the workingOrderData dict, or raises PreviewError if not found.
        """
        response = await self.client.get("/workingorders")
        body = response.json()
        orders = body.get("workingOrders", []) if isinstance(body, dict) else []
        for item in orders:
            data = item.get("workingOrderData", {}) if isinstance(item, dict) else {}
            if data.get("dealId") == deal_id:
                return data
        raise PreviewError(f"Working order '{deal_id}' not found", code="ORDER_NOT_FOUND")

    @staticmethod
    def _resolve_scalar_field(
        request: UpdateWorkingOrderRequest,
        existing: dict[str, Any],
        snake: str,
        existing_key: str,
        signed: bool,
    ) -> Any:
        """Return the override, the carried-forward existing value, or None.

        GET returns stopDistance/profitDistance signed by direction; PUT rejects
        negatives. Take abs() on those when carrying forward.
        """
        override = getattr(request, snake)
        if override is not None:
            return override
        existing_value = existing.get(existing_key)
        if existing_value is None:
            return None
        if signed and isinstance(existing_value, int | float):
            return abs(existing_value)
        return existing_value

    @staticmethod
    def _resolve_time_in_force(request: UpdateWorkingOrderRequest, existing: dict[str, Any]) -> str:
        """Resolve effective timeInForce — override > existing > default GTC.

        The upstream wipes the expiry to GOOD_TILL_CANCELLED when timeInForce
        is omitted from the PUT body, so the field must always be present.
        """
        if request.time_in_force is not None:
            return request.time_in_force.value
        return existing.get("timeInForce") or "GOOD_TILL_CANCELLED"

    @staticmethod
    def _resolve_good_till_date(
        request: UpdateWorkingOrderRequest, existing: dict[str, Any]
    ) -> str | None:
        """Resolve goodTillDate carry-forward from goodTillDateUTC.

        Reading from the local-time goodTillDate would drift by the tz offset
        on every update — the canonical UTC field is goodTillDateUTC.
        """
        if request.good_till_date is not None:
            return request.good_till_date
        utc = existing.get("goodTillDateUTC")
        return utc if utc is not None else None

    @staticmethod
    def _build_update_payload(
        request: UpdateWorkingOrderRequest,
        existing: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the broker payload for a working-order update.

        PUT replaces the resource — any field missing from the body is wiped
        by Capital.com. Carry forward scalar fields from the existing order
        when the caller did not override them. (GET /workingorders does not
        return stopAmount/profitAmount, so those cannot be carried forward
        and must be re-supplied by the caller or they will be lost.)
        """
        guaranteed = request.guaranteed_stop
        if guaranteed is None:
            guaranteed = bool(existing.get("guaranteedStop", False))
        trailing = request.trailing_stop
        if trailing is None:
            trailing = bool(existing.get("trailingStop", False))

        payload: dict[str, Any] = {
            "guaranteedStop": guaranteed,
            "trailingStop": trailing,
            "timeInForce": RiskEngine._resolve_time_in_force(request, existing),
        }

        for snake, camel, existing_key, signed in (
            ("level", "level", "orderLevel", False),
            ("stop_level", "stopLevel", "stopLevel", False),
            ("stop_distance", "stopDistance", "stopDistance", True),
            ("profit_level", "profitLevel", "profitLevel", False),
            ("profit_distance", "profitDistance", "profitDistance", True),
        ):
            value = RiskEngine._resolve_scalar_field(request, existing, snake, existing_key, signed)
            if value is not None:
                payload[camel] = value

        if payload["timeInForce"] == "GOOD_TILL_DATE":
            gtd = RiskEngine._resolve_good_till_date(request, existing)
            if gtd is not None:
                payload["goodTillDate"] = gtd

        for snake, camel in (("stop_amount", "stopAmount"), ("profit_amount", "profitAmount")):
            override = getattr(request, snake)
            if override is not None:
                payload[camel] = override

        return payload

    async def preview_working_order_update(
        self, request: UpdateWorkingOrderRequest
    ) -> PreviewResult:
        """Preview an update to a pending working order.

        Carries forward existing guaranteed_stop / trailing_stop values
        because Capital.com resets omitted flags to false.
        """
        existing = await self._fetch_working_order(request.deal_id)

        checks: list[RiskCheck] = []

        # Check 1: Trading enabled
        if not self.config.cap_allow_trading:
            checks.append(
                RiskCheck(
                    check="trading_enabled",
                    passed=False,
                    message="Trading is disabled (CAP_ALLOW_TRADING=false)",
                )
            )
            return PreviewResult(normalized_request={}, checks=checks, all_checks_passed=False)
        checks.append(RiskCheck(check="trading_enabled", passed=True, message="Trading is enabled"))

        # Check 2: Epic allowlist (epic comes from existing order — caller cannot change it via PUT)
        existing_epic = str(existing.get("epic", ""))
        if not self.config.is_epic_allowed(existing_epic):
            checks.append(
                RiskCheck(
                    check="epic_allowed",
                    passed=False,
                    message=f"Epic '{existing_epic}' not in allowlist",
                )
            )
            return PreviewResult(normalized_request={}, checks=checks, all_checks_passed=False)
        epic = existing_epic.upper()
        checks.append(
            RiskCheck(check="epic_allowed", passed=True, message=f"Epic '{epic}' is allowed")
        )

        # Check 3: Daily order limit
        daily_check = self._check_daily_limit()
        checks.append(daily_check)
        if not daily_check.passed:
            return PreviewResult(normalized_request={}, checks=checks, all_checks_passed=False)

        broker_payload = self._build_update_payload(request, existing)

        normalized_request: dict[str, Any] = {
            "deal_id": request.deal_id,
            "epic": epic,
            "broker_payload": broker_payload,
        }

        result = PreviewResult(
            normalized_request=normalized_request,
            checks=checks,
            all_checks_passed=all(c.passed for c in checks),
            estimated_risk_notes=(
                "Update preview only; omitted fields carried forward from existing order. "
                "stop_amount / profit_amount cannot be carried forward — re-supply them "
                "explicitly if previously set."
            ),
        )
        self._preview_cache[result.preview_id] = result
        logger.info(
            f"Created update preview {result.preview_id} for working order {request.deal_id}"
        )
        return result

    def get_preview(self, preview_id: str) -> PreviewResult:
        """
        Get a cached preview result.

        Args:
            preview_id: Preview ID

        Returns:
            Preview result

        Raises:
            PreviewError: If preview not found or expired
        """
        preview = self._preview_cache.get(preview_id)

        if not preview:
            raise PreviewError(f"Preview {preview_id} not found", code="PREVIEW_NOT_FOUND")

        if preview.is_expired(self.config.cap_preview_cache_ttl_s):
            del self._preview_cache[preview_id]
            raise PreviewError(f"Preview {preview_id} expired", code="PREVIEW_EXPIRED")

        return preview

    def consume_preview(self, preview_id: str) -> None:
        """Remove a preview from cache after successful execution."""
        if preview_id in self._preview_cache:
            del self._preview_cache[preview_id]
            logger.info(f"Consumed preview {preview_id}")

    def validate_execution_guards(self, *, confirm: bool, preview_id: str | None = None) -> None:
        """
        Validate execution guards before trade execution.

        Args:
            confirm: Explicit confirmation flag
            preview_id: Optional preview ID to validate

        Raises:
            TradingDisabledError: If trading is disabled
            DryRunError: If dry-run mode is enabled
            ConfirmRequiredError: If confirmation is required but not provided
            PreviewError: If preview not found or checks failed
        """
        # Guard 1: Trading enabled
        if not self.config.cap_allow_trading:
            raise TradingDisabledError()

        # Guard 2: Dry-run mode
        if self.config.cap_dry_run:
            raise DryRunError()

        # Guard 3: Explicit confirmation
        if self.config.cap_require_explicit_confirm and not confirm:
            raise ConfirmRequiredError()

        # Guard 4: Preview validation
        if preview_id:
            preview = self.get_preview(preview_id)
            if not preview.all_checks_passed:
                raise PreviewError(
                    "Preview checks failed, cannot execute",
                    code="PREVIEW_CHECKS_FAILED",
                )


# Global risk engine instance
_risk_engine: RiskEngine | None = None


def get_risk_engine() -> RiskEngine:
    """Get or create the global risk engine instance."""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine


def reset_risk_engine() -> None:
    """Reset the global risk engine (mainly for testing)."""
    global _risk_engine
    _risk_engine = None
