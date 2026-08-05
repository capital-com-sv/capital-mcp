"""HTTP client wrapper for Capital.com API."""

import logging
from typing import Any

import httpx

from . import __version__
from .config import get_config
from .errors import SessionError, UpstreamError, redact_secrets
from .models import SessionTokens
from .rate_limit import get_rate_limiter

USER_AGENT = f"capital-com-mcp/{__version__}"

logger = logging.getLogger(__name__)


class CapitalClient:
    """HTTP client for Capital.com REST API."""

    def __init__(self) -> None:
        self.config = get_config()
        self.rate_limiter = get_rate_limiter()
        self.session_tokens: SessionTokens | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_base_url,
                timeout=httpx.Timeout(self.config.cap_http_timeout_s),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        headers: dict[str, str] = {}

        # Add API key header for session creation
        headers["X-CAP-API-KEY"] = self.config.cap_api_key

        # Add session tokens if available
        if self.session_tokens:
            headers["CST"] = self.session_tokens.cst
            headers["X-SECURITY-TOKEN"] = self.session_tokens.x_security_token
            self.session_tokens.update_last_used()

        return headers

    def _log_request(self, method: str, url: str, **kwargs: Any) -> None:
        """Log HTTP request (with secret redaction)."""
        if logger.isEnabledFor(logging.DEBUG):
            safe_kwargs = {
                k: redact_secrets(v) if isinstance(v, dict) else v for k, v in kwargs.items()
            }
            logger.debug(f"Request: {method} {url} UA={USER_AGENT} {safe_kwargs}")

    def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response (with secret redaction)."""
        if logger.isEnabledFor(logging.DEBUG):
            try:
                body = response.json()
                safe_body = redact_secrets(body) if isinstance(body, dict) else body
                logger.debug(f"Response: {response.status_code} {safe_body}")
            except Exception:
                logger.debug(f"Response: {response.status_code} (non-JSON)")

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        rate_limit_type: str = "global",
        retry_on_auth_error: bool = True,
        max_retries: int = 3,
    ) -> httpx.Response:
        """
        Make HTTP request with rate limiting and error handling.

        Args:
            method: HTTP method
            path: API path (e.g., "/markets")
            json: JSON body
            params: Query parameters
            rate_limit_type: Type of rate limiting ("global", "session", "trading")
            retry_on_auth_error: Whether to retry on auth errors
            max_retries: Max retries for safe operations (GETs)

        Returns:
            HTTP response

        Raises:
            UpstreamError: On HTTP errors
            SessionError: On auth errors
        """
        # Acquire rate limit token
        if rate_limit_type == "session":
            acquired = await self.rate_limiter.acquire_session()
        elif rate_limit_type == "trading":
            acquired = await self.rate_limiter.acquire_trading()
        else:
            acquired = await self.rate_limiter.acquire_global()

        if not acquired:
            from .errors import RateLimitError

            raise RateLimitError("Rate limit timeout")

        # Prepare request
        client = self._get_client()
        headers = self._get_auth_headers()
        url = path

        self._log_request(method, url, json=json, params=params)

        # Retry logic
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=headers,
                )

                self._log_response(response)

                # Handle auth errors
                if response.status_code in (401, 403):
                    if retry_on_auth_error and attempt == 0:
                        logger.warning("Auth error, session may have expired")
                        raise SessionError("Session expired or invalid", code="SESSION_EXPIRED")
                    raise SessionError(
                        f"Authentication failed: {response.status_code}",
                        code="AUTH_FAILED",
                    )

                # Handle other errors
                if response.status_code >= 400:
                    error_body = None
                    error_message = response.reason_phrase or "Error"

                    try:
                        error_body = response.text
                        # Try to extract error from JSON response
                        if error_body:
                            try:
                                error_json = response.json()
                                # Capital.com returns {"errorCode": "message"}
                                if isinstance(error_json, dict) and "errorCode" in error_json:
                                    error_message = error_json["errorCode"]
                                # Or it might be {"error": "...", "message": "..."}
                                elif isinstance(error_json, dict):
                                    if "message" in error_json:
                                        error_message = error_json["message"]
                                    elif "error" in error_json:
                                        error_message = error_json["error"]
                                    else:
                                        # Use full JSON as string
                                        error_message = str(error_json)
                            except Exception:
                                # If JSON parsing fails, use raw text (truncate long responses)
                                if len(error_body) > 200:
                                    error_message = error_body[:200] + "..."
                                else:
                                    error_message = error_body
                    except Exception:
                        pass

                    raise UpstreamError(
                        f"HTTP {response.status_code}: {error_message}",
                        status_code=response.status_code,
                        response_body=error_body,
                    )

                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                logger.warning(f"Request timeout/error (attempt {attempt + 1}/{max_retries}): {e}")

                # Only retry safe operations (GETs)
                if method.upper() != "GET" or attempt >= max_retries - 1:
                    break

                # Exponential backoff
                import asyncio

                await asyncio.sleep(min(2**attempt, 10))

        # All retries failed
        if last_exception:
            raise UpstreamError(
                f"Request failed after {max_retries} attempts: {str(last_exception)}"
            )

        raise UpstreamError("Request failed for unknown reason")

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        """Make GET request."""
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        rate_limit_type: str = "global",
    ) -> httpx.Response:
        """Make POST request."""
        return await self.request(
            "POST",
            path,
            json=json,
            rate_limit_type=rate_limit_type,
            max_retries=1,  # No retries for POSTs
        )

    async def put(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        """Make PUT request."""
        return await self.request(
            "PUT",
            path,
            json=json,
            max_retries=1,  # No retries for PUTs
        )

    async def update_working_order(self, deal_id: str, payload: dict[str, Any]) -> httpx.Response:
        """PUT /workingorders/{dealId} — amend a pending working order."""
        return await self.put(f"/workingorders/{deal_id}", json=payload)

    async def delete(self, path: str) -> httpx.Response:
        """Make DELETE request."""
        return await self.request(
            "DELETE",
            path,
            max_retries=1,  # No retries for DELETEs
        )


# Global client instance
_client: CapitalClient | None = None


def get_client() -> CapitalClient:
    """Get or create the global client instance."""
    global _client
    if _client is None:
        _client = CapitalClient()
    return _client


async def close_client() -> None:
    """Close the global client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def reset_client() -> None:
    """Reset the global client (mainly for testing)."""
    global _client
    _client = None
