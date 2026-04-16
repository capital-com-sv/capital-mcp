"""WebSocket client for Capital.com streaming API."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from .config import get_config
from .errors import SessionError, UpstreamError
from .models import PriceTick
from .session import get_session_manager

logger = logging.getLogger(__name__)

# Singleton instance
_websocket_client: Optional["WebSocketClient"] = None


def get_websocket_client() -> "WebSocketClient":
    """Get or create WebSocket client singleton."""
    global _websocket_client
    if _websocket_client is None:
        _websocket_client = WebSocketClient()
    return _websocket_client


class WebSocketClient:
    """
    WebSocket client for Capital.com streaming API.

    Handles real-time price streaming with authentication, subscription management,
    and automatic reconnection.

    Protocol: JSON messages with {destination, correlationId, cst, securityToken, payload}.
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.session_manager = get_session_manager()
        self._ws: ClientConnection | None = None
        self._subscribed_epics: set[str] = set()
        self._last_ping: datetime | None = None

    async def __aenter__(self) -> "WebSocketClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def _get_tokens(self) -> tuple[str, str]:
        """Get current session tokens for message authentication."""
        tokens = self.session_manager.client.session_tokens
        if not tokens:
            raise SessionError("No session tokens available.")
        return tokens.cst, tokens.x_security_token

    def _build_message(self, destination: str, payload: dict[str, Any]) -> str:
        """Build a JSON message in Capital.com WebSocket protocol format."""
        cst, security_token = self._get_tokens()
        msg = {
            "destination": destination,
            "correlationId": str(uuid.uuid4()),
            "cst": cst,
            "securityToken": security_token,
            "payload": payload,
        }
        return json.dumps(msg)

    async def connect(self) -> None:
        """
        Connect to Capital.com WebSocket API.

        Raises:
            SessionError: If WebSocket is disabled or authentication fails
            UpstreamError: If connection fails
        """
        if not self.config.cap_ws_enabled:
            raise SessionError(
                "WebSocket streaming is disabled. Set CAP_WS_ENABLED=true to enable."
            )

        # Ensure we have valid session tokens
        await self.session_manager.ensure_logged_in()
        status = self.session_manager.get_status()

        if not status.logged_in or not self.session_manager.client.session_tokens:
            raise SessionError("Not logged in. Cannot establish WebSocket connection.")

        ws_url = self.config.ws_url

        try:
            logger.info(f"Connecting to WebSocket: {ws_url}")

            self._ws = await websockets.connect(
                ws_url,
                ping_interval=None,
                close_timeout=5,
            )

            self._last_ping = datetime.now(timezone.utc)
            logger.info("WebSocket connected successfully")

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise UpstreamError(f"Failed to connect to WebSocket: {e}") from e

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            logger.info("Closing WebSocket connection")
            await self._ws.close()
            self._ws = None
            self._subscribed_epics.clear()
            self._last_ping = None

    async def subscribe(self, epics: list[str]) -> None:
        """
        Subscribe to price updates for given EPICs.

        Args:
            epics: List of market EPICs (max 40 per Capital.com limits)

        Raises:
            ValueError: If too many EPICs requested
            SessionError: If not connected
        """
        if len(epics) > 40:
            raise ValueError(f"Cannot subscribe to more than 40 EPICs (requested: {len(epics)})")

        if not self._ws:
            raise SessionError("WebSocket not connected. Call connect() first.")

        msg = self._build_message("marketData.subscribe", {"epics": epics})

        try:
            await self._ws.send(msg)
            self._subscribed_epics.update(epics)
            logger.debug(f"Subscribed to {epics}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {epics}: {e}")
            raise UpstreamError(f"Subscription failed: {e}") from e

    async def unsubscribe(self, epics: list[str]) -> None:
        """
        Unsubscribe from price updates.

        Args:
            epics: List of market EPICs to unsubscribe from
        """
        if not self._ws:
            return

        epics_to_unsub = [e for e in epics if e in self._subscribed_epics]
        if not epics_to_unsub:
            return

        msg = self._build_message("marketData.unsubscribe", {"epics": epics_to_unsub})

        try:
            await self._ws.send(msg)
            for epic in epics_to_unsub:
                self._subscribed_epics.discard(epic)
            logger.debug(f"Unsubscribed from {epics_to_unsub}")
        except Exception as e:
            logger.warning(f"Failed to unsubscribe: {e}")

    async def _send_ping(self) -> None:
        """Send ping to keep connection alive."""
        if self._ws:
            try:
                msg = self._build_message("ping", {})
                await self._ws.send(msg)
                self._last_ping = datetime.now(timezone.utc)
                logger.debug("Sent WebSocket ping")
            except Exception as e:
                logger.warning(f"Failed to send ping: {e}")

    async def _should_ping(self) -> bool:
        """Check if we should send a ping (every 5 minutes)."""
        if not self._last_ping:
            return True

        elapsed = (datetime.now(timezone.utc) - self._last_ping).total_seconds()
        return elapsed >= 300  # 5 minutes

    def _parse_message(self, message: str) -> PriceTick | None:
        """
        Parse incoming WebSocket message.

        Args:
            message: Raw JSON message from WebSocket

        Returns:
            PriceTick if it's a price update, None otherwise
        """
        try:
            data = json.loads(message)

            if not isinstance(data, dict):
                return None

            destination = data.get("destination", "")
            status = data.get("status", "")

            # Price quote: {"status": "OK", "destination": "quote", "payload": {...}}
            if destination == "quote" and status == "OK":
                payload = data.get("payload", {})
                epic = payload.get("epic")
                bid = payload.get("bid")
                ofr = payload.get("ofr")

                if epic and bid is not None and ofr is not None:
                    timestamp = payload.get("timestamp")
                    ts_str = (
                        datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                        if timestamp
                        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    )

                    return PriceTick(
                        epic=epic,
                        bid=float(bid),
                        offer=float(ofr),
                        timestamp=ts_str,
                        change_percent=None,
                    )

            # Log non-quote messages for debugging
            if destination not in ("quote", ""):
                logger.debug(f"WS message: destination={destination}, status={status}")

            return None

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse WebSocket message: {e}")
            return None

    async def stream(
        self, duration: float = 300.0, reconnect_attempts: int = 3
    ) -> AsyncIterator[PriceTick]:
        """
        Stream price updates.

        Args:
            duration: Stream duration in seconds (default: 5 minutes)
            reconnect_attempts: Number of reconnection attempts on disconnect

        Yields:
            PriceTick objects as they arrive

        Raises:
            SessionError: If not connected
            UpstreamError: If connection fails after retries
        """
        if not self._ws:
            raise SessionError("WebSocket not connected. Call connect() first.")

        start_time = datetime.now(timezone.utc)
        reconnect_count = 0

        try:
            while True:
                # Check duration timeout
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= duration:
                    logger.info(f"Stream duration {duration}s reached, stopping")
                    break

                # Send ping if needed
                if await self._should_ping():
                    await self._send_ping()

                try:
                    # Receive message with timeout
                    remaining = duration - elapsed
                    timeout = min(remaining, 10.0)  # Max 10s wait per message

                    raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
                    message = raw.decode("utf-8") if isinstance(raw, bytes) else raw

                    logger.debug(f"WS recv: {message[:200]}")

                    # Parse and yield price tick
                    tick = self._parse_message(message)
                    if tick:
                        yield tick

                except asyncio.TimeoutError:
                    # No message received, continue (normal for quiet periods)
                    continue

                except websockets.exceptions.ConnectionClosed:
                    # Connection lost, attempt reconnection
                    if reconnect_count < reconnect_attempts:
                        reconnect_count += 1
                        logger.warning(
                            f"WebSocket disconnected, reconnecting "
                            f"({reconnect_count}/{reconnect_attempts})"
                        )

                        await asyncio.sleep(2**reconnect_count)  # Exponential backoff

                        # Reconnect and resubscribe
                        epics_to_restore = list(self._subscribed_epics)
                        await self.close()
                        await self.connect()
                        await self.subscribe(epics_to_restore)

                        logger.info("Reconnection successful")
                    else:
                        logger.error(f"Max reconnection attempts ({reconnect_attempts}) reached")
                        raise UpstreamError(
                            "WebSocket connection lost and reconnection failed"
                        ) from None

        finally:
            # Cleanup: unsubscribe from all EPICs
            if self._subscribed_epics:
                await self.unsubscribe(list(self._subscribed_epics))
