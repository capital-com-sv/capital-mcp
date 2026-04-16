"""Session management for Capital.com API."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from .capital_client import get_client
from .config import get_config
from .errors import SessionError
from .models import SessionStatus, SessionTokens

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session lifecycle for Capital.com API.

    Handles:
    - Login (POST /session)
    - Token storage (CST, X-SECURITY-TOKEN)
    - Auto-refresh on expiry
    - Keep-alive (GET /ping)
    - Logout (DELETE /session)
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.client = get_client()
        self.tokens: SessionTokens | None = None
        self.account_id: str | None = None
        self._login_lock = asyncio.Lock()

    async def login(self, *, force: bool = False, account_id: str | None = None) -> dict[str, Any]:
        """
        Create a new session.

        Args:
            force: Force login even if session is valid
            account_id: Account ID to switch to after login

        Returns:
            Login response data
        """
        async with self._login_lock:
            # Check if already logged in
            if not force and self.tokens and not self.tokens.is_expired():
                logger.debug("Session still valid, skipping login")
                return {"message": "Session already active"}

            logger.info(f"Logging in to {self.config.cap_env.value} environment")

            # Prepare login request
            login_data = {
                "identifier": self.config.cap_identifier,
                "password": self.config.cap_api_password,
                "encryptedPassword": False,
            }

            try:
                # POST /session with special rate limit
                response = await self.client.post(
                    "/session",
                    json=login_data,
                    rate_limit_type="session",
                )

                # Extract tokens from headers
                cst = response.headers.get("CST")
                x_security_token = response.headers.get("X-SECURITY-TOKEN")

                if not cst or not x_security_token:
                    raise SessionError("Login response missing required tokens")

                # Store tokens
                self.tokens = SessionTokens(
                    cst=cst,
                    x_security_token=x_security_token,
                )

                # Update client tokens
                self.client.session_tokens = self.tokens

                # Parse response body
                response_data = response.json()

                # Extract account ID if present
                if "currentAccountId" in response_data:
                    self.account_id = response_data["currentAccountId"]

                logger.info(f"Login successful, account: {self.account_id}")

                # Switch account if requested
                target_account = account_id or self.config.cap_default_account_id
                if target_account and target_account != self.account_id:
                    await self.switch_account(target_account)

                return dict(response_data)

            except Exception as e:
                logger.error(f"Login failed: {e}")
                self.tokens = None
                self.client.session_tokens = None
                raise

    async def switch_account(self, account_id: str) -> dict[str, Any]:
        """
        Switch to a different account.

        Args:
            account_id: Target account ID

        Returns:
            Response data
        """
        if not self.tokens:
            raise SessionError("Not logged in", code="SESSION_NOT_INITIALIZED")

        logger.info(f"Switching to account: {account_id}")

        response = await self.client.put(
            "/session",
            json={"accountId": account_id},
        )

        # Update stored account ID
        self.account_id = account_id

        result: dict[str, Any] = response.json()
        return result

    async def ping(self) -> dict[str, Any]:
        """
        Keep session alive.

        Returns:
            Ping response
        """
        if not self.tokens:
            raise SessionError("Not logged in", code="SESSION_NOT_INITIALIZED")

        logger.debug("Pinging session")
        response = await self.client.get("/ping")
        return response.json() if response.text else {"status": "ok"}

    async def logout(self) -> None:
        """End session and clear tokens."""
        if not self.tokens:
            logger.debug("Not logged in, nothing to logout")
            return

        try:
            logger.info("Logging out")
            await self.client.delete("/session")
        except Exception as e:
            logger.warning(f"Logout request failed: {e}")
        finally:
            # Clear tokens regardless of response
            self.tokens = None
            self.account_id = None
            self.client.session_tokens = None

    async def ensure_logged_in(self) -> None:
        """Ensure session is active, refresh if needed."""
        if not self.tokens:
            logger.info("No session, logging in")
            await self.login()
            return

        if self.tokens.is_expired():
            logger.info("Session expired, re-logging in")
            await self.login(force=True)

    def get_status(self) -> SessionStatus:
        """Get current session status."""
        if not self.tokens:
            return SessionStatus(
                env=self.config.cap_env.value,
                base_url=self.config.base_url,
                logged_in=False,
            )

        # Calculate expiry estimate
        age = (datetime.utcnow() - self.tokens.last_used_at).total_seconds()
        expires_in = max(0, int(540 - age))  # 9 minutes = 540 seconds

        return SessionStatus(
            env=self.config.cap_env.value,
            base_url=self.config.base_url,
            logged_in=True,
            account_id=self.account_id,
            last_used_at=self.tokens.last_used_at.isoformat() + "Z",
            expires_in_s_estimate=expires_in,
        )


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager() -> None:
    """Reset the global session manager (mainly for testing)."""
    global _session_manager
    _session_manager = None
