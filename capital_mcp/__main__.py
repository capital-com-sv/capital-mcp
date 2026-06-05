"""Allow running as `python -m capital_mcp`."""

from capital_mcp.server import get_config, logger, mcp

config = get_config()
logger.info(f"Starting Capital.com MCP Server (env: {config.cap_env.value})")
logger.info(f"Trading enabled: {config.cap_allow_trading}")

if config.cap_allow_trading:
    allowed = config.allowed_epics_list
    if allowed and allowed[0].upper() == "ALL":
        logger.info("Allowed EPICs: ALL (no restrictions)")
    else:
        logger.info(f"Allowed EPICs: {allowed}")

mcp.run()
