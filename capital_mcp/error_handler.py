"""Error handler middleware for user-friendly error responses."""

import logging
import time

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult
from mcp import types as mt
from pydantic import ValidationError

from .errors import (
    CapitalMCPError,
    ConfirmRequiredError,
    PreviewError,
)

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(Middleware):
    """Intercepts exceptions from tool calls and returns user-friendly messages."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        logger.info("Executing tool: %s", tool_name)
        start = time.perf_counter()
        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info("Tool completed: %s (%.0fms)", tool_name, duration_ms)
            return result
        except ValidationError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning("Tool failed: %s (%.0fms) - validation error", tool_name, duration_ms)
            message = self.format_validation_error(e)
            return ToolResult(
                content=message,
                structured_content={"error": message},
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "Tool failed: %s (%.0fms) - %s", tool_name, duration_ms, type(e).__name__
            )
            message = self.format_error(e)
            return ToolResult(
                content=message,
                structured_content={"error": message},
            )

    def format_validation_error(self, error: ValidationError) -> str:
        """Format Pydantic ValidationError into user-friendly message."""
        messages = []
        for err in error.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            messages.append(f"Invalid {field}: {msg}")
        return ". ".join(messages) + "."

    def format_error(self, error: Exception) -> str:
        """Format any exception into user-friendly message."""
        # Unwrap chained exceptions (FastMCP wraps errors in ToolError)
        original = error.__cause__ if error.__cause__ else error

        if isinstance(original, PreviewError):
            code = getattr(original, "code", "")
            if code == "PREVIEW_NOT_FOUND":
                return "No valid trade preview found. Please preview your trade first."
            if code == "PREVIEW_EXPIRED":
                return "This trade preview has expired. Please create a new preview."
            return str(original)

        if isinstance(original, ConfirmRequiredError):
            return "Trade execution requires explicit confirmation. Please confirm to proceed."

        if isinstance(original, CapitalMCPError):
            return str(original)

        return f"Unexpected error: {type(original).__name__}: {str(original)}"
