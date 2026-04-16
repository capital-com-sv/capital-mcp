# Capital.com MCP Server - Usage Guide

Complete guide for using the Capital.com MCP Server with LLMs.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Client Integration](#client-integration)
5. [Available Tools](#available-tools)
6. [Common Workflows](#common-workflows)
7. [Safety & Risk Management](#safety--risk-management)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Capital.com Account Setup

1. **Create Account**: [https://capital.com/trading/signup](https://capital.com/trading/signup)
   - Choose **Demo** for testing (recommended to start)
   - Verify email address

2. **Enable Two-Factor Authentication (2FA)**:
   - Go to: Settings > Security > Two-Factor Authentication
   - Follow setup instructions
   - **Required** before generating API keys

3. **Generate API Key**:
   - Go to: Settings > API integrations
   - Click "Generate new key"
   - Set a label (e.g., "MCP Server")
   - **Set custom password** (NOT your platform password)
   - **Save the API key** (shown only once!)
   - **Important**: API keys have full trading access; no read-only option available

### System Requirements

- Python 3.10 or higher
- pip (Python package manager)
- Virtual environment (recommended)
- 100MB disk space

---

## Installation

```bash
# Clone/download the project
cd /path/to/capital-mcp

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import capital_mcp; print('Installation successful!')"
```

---

## Configuration

### Method 1: Environment File (.env)

```bash
# Copy example file
cp .env.example .env

# Edit .env
nano .env  # or use your preferred editor
```

Required variables:
```bash
CAP_ENV=demo                           # demo or live
CAP_API_KEY=your_api_key_here          # From Capital.com
CAP_IDENTIFIER=your_email@example.com  # Your login email
CAP_API_PASSWORD=your_custom_password  # API key password
```

Safety variables (recommended):
```bash
CAP_ALLOW_TRADING=false                # Enable trading (default: false)
CAP_ALLOWED_EPICS=                     # Allowlist (empty = block all)
CAP_MAX_POSITION_SIZE=1.0              # Max position size
CAP_MAX_WORKING_ORDER_SIZE=1.0         # Max order size
CAP_MAX_OPEN_POSITIONS=3               # Max concurrent positions
CAP_MAX_ORDERS_PER_DAY=20              # Daily order limit
CAP_REQUIRE_EXPLICIT_CONFIRM=true      # Require confirm=true
CAP_DRY_RUN=false                      # Block all executions
```

### Method 2: MCP Client Configuration

Configure directly in your MCP client (Claude Desktop, Cursor, etc.) - see [Client Integration](#client-integration) section.

---

## Client Integration

### Claude Desktop

**macOS:**
```bash
# Edit config file
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Linux:**
```bash
# Edit config file
nano ~/.config/Claude/claude_desktop_config.json
```

**Windows:**
```
Edit: %APPDATA%\Claude\claude_desktop_config.json
```

**Configuration:**
```json
{
  "mcpServers": {
    "capital-com": {
      "command": "/FULL/PATH/TO/capital-mcp/venv/bin/python",
      "args": ["-m", "capital_mcp.server"],
      "env": {
        "CAP_ENV": "demo",
        "CAP_API_KEY": "your_api_key_here",
        "CAP_IDENTIFIER": "your_email@example.com",
        "CAP_API_PASSWORD": "your_custom_password",
        "CAP_ALLOW_TRADING": "false",
        "CAP_ALLOWED_EPICS": "",
        "CAP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Get Python path:**
```bash
cd /path/to/capital-mcp
source venv/bin/activate
which python  # Copy this path to "command" field
```

**Windows path format:** `"C:\\Users\\YourName\\capital-mcp\\venv\\Scripts\\python.exe"`

**Restart Claude Desktop** after editing config.

### Cursor IDE

1. Open Settings: `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux)
2. Search for "MCP" in settings
3. Click "Configure MCP Servers"
4. Add same configuration as Claude Desktop
5. Restart Cursor

### Windsurf

```bash
# Create config directory
mkdir -p ~/.windsurf/mcp

# Create config file
nano ~/.windsurf/mcp/servers.json
```

Use same JSON configuration as Claude Desktop.

### Other MCP-Compatible Clients

Any MCP client supporting STDIO transport can use this server:

1. Spawn process: `python -m capital_mcp.server`
2. Set environment variables
3. Communicate via STDIN/STDOUT with JSON-RPC

---

## Available Tools

### Session Management (4 tools)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_session_status` | Get session status, login state, account ID | No |
| `cap_session_login` | Create new session, force re-login | No |
| `cap_session_ping` | Keep session alive (extends timeout) | Yes |
| `cap_session_logout` | End session, clear tokens | Yes |

### Market Data (6 tools)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_market_search` | Search markets by term or EPICs | Yes |
| `cap_market_get` | Get detailed market info + dealing rules | Yes |
| `cap_market_navigation_root` | Get market category tree root | Yes |
| `cap_market_navigation_node` | Get specific category node | Yes |
| `cap_market_prices` | Get historical OHLC candle data | Yes |
| `cap_market_sentiment` | Get client sentiment (long/short %) | Yes |

### Account Management (6 tools)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_account_list` | List all trading accounts | Yes |
| `cap_account_preferences_get` | Get hedging mode & leverage settings | Yes |
| `cap_account_preferences_set` | Set hedging/leverage (TRADE-GATED) | Yes |
| `cap_account_history_activity` | Get account activity history | Yes |
| `cap_account_history_transactions` | Get transaction history | Yes |
| `cap_account_demo_topup` | Top up demo balance (DEMO ONLY) | Yes |

### Trading - Read-Only (5 tools)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_trade_positions_list` | List all open positions | Yes |
| `cap_trade_positions_get` | Get specific position details | Yes |
| `cap_trade_orders_list` | List all working orders | Yes |
| `cap_trade_confirm_get` | Get deal confirmation status | Yes |
| `cap_trade_confirm_wait` | Wait for confirmation with polling | Yes |

### Trading - Preview (2 tools, SAFE)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_trade_preview_position` | Preview position (NO SIDE EFFECTS) | Yes |
| `cap_trade_preview_working_order` | Preview working order (NO SIDE EFFECTS) | Yes |

### Trading - Execute (7 tools, DANGEROUS)

| Tool | Description | Auth Required | Trading Gated |
|------|-------------|---------------|---------------|
| `cap_trade_execute_position` | Execute position (CREATES TRADE) | Yes | Yes |
| `cap_trade_execute_working_order` | Execute order (CREATES ORDER) | Yes | Yes |
| `cap_trade_positions_close` | Close position (CLOSES TRADE) | Yes | Yes |
| `cap_trade_orders_cancel` | Cancel order (CANCELS ORDER) | Yes | Yes |

### WebSocket Streaming (3 tools)

| Tool | Description | Auth Required | WS Enabled |
|------|-------------|---------------|------------|
| `cap_stream_prices` | Stream real-time price updates (max 40 EPICs) | Yes | Yes |
| `cap_stream_alerts` | Monitor markets for alert conditions | Yes | Yes |
| `cap_stream_portfolio` | Stream real-time P&L for open positions | Yes | Yes |

### Watchlists (6 tools)

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `cap_watchlists_list` | List all watchlists | Yes |
| `cap_watchlists_get` | Get watchlist with markets | Yes |
| `cap_watchlists_create` | Create new watchlist | Yes |
| `cap_watchlists_add_market` | Add market to watchlist | Yes |
| `cap_watchlists_delete` | Delete watchlist | Yes |
| `cap_watchlists_remove_market` | Remove market from watchlist | Yes |

**Total: 36 tools implemented**

---

## Common Workflows

### 1. Getting Started

```
You: "Check my Capital.com session status"
→ cap_session_status

You: "Login to Capital.com"
→ cap_session_login

You: "List my accounts"
→ cap_account_list
```

### 2. Market Research

```
You: "Search for gold markets"
→ cap_market_search (search_term="gold")

You: "Get details for GOLD market"
→ cap_market_get (epic="GOLD")

You: "Show me last 100 daily candles for GOLD"
→ cap_market_prices (epic="GOLD", resolution="DAY", max=100)

You: "What's the client sentiment on GOLD?"
→ cap_market_sentiment (market_id="GOLD")
```

### 3. Portfolio Monitoring

```
You: "Show all my open positions"
→ cap_trade_positions_list

You: "Show my working orders"
→ cap_trade_orders_list

You: "Get details for position ABC123"
→ cap_trade_positions_get (deal_id="ABC123")

You: "Show recent account activity"
→ cap_account_history_activity (lastPeriod=3600)
```

### 4. Safe Trading (Preview → Execute)

**Step 1: Enable trading** (edit .env):
```bash
CAP_ALLOW_TRADING=true
CAP_ALLOWED_EPICS=SILVER,GOLD
```

Restart your MCP client.

**Step 2: Preview trade:**
```
You: "Preview buying 1.0 SILVER with stop loss at 24.50"
→ cap_trade_preview_position
  - epic: "SILVER"
  - direction: "BUY"
  - size: 1.0
  - stop_level: 24.50

Response includes:
- preview_id: "abc-123..."
- normalized_request: {...}
- checks: [...]
- all_checks_passed: true/false
- estimated_entry: 25.10
```

**Step 3: Review checks:**
- ✅ Trading enabled
- ✅ SILVER in allowlist
- ✅ Size within limits
- ✅ Daily order limit OK
- ✅ Size normalized to broker increments

**Step 4: Execute (if checks pass):**
```
You: "Execute position with preview_id abc-123... and confirm=true"
→ cap_trade_execute_position
  - preview_id: "abc-123..."
  - confirm: true
  - wait_for_confirm: true

Response includes:
- dealReference: "o_456..."
- confirmation: {status: "ACCEPTED", ...}
- affectedDeals: [{dealId: "DEF789", ...}]
```

**Step 5: Monitor:**
```
You: "Show my positions"
→ Position opened with ID: DEF789

You: "Close position DEF789 with confirm=true"
→ cap_trade_positions_close
  - deal_id: "DEF789"
  - confirm: true
```

### 5. Working with Watchlists

```
You: "Show my watchlists"
→ cap_watchlists_list

You: "Create watchlist called 'Crypto'"
→ cap_watchlists_create (name="Crypto", confirm=true)

You: "Add BTCUSD to watchlist [id]"
→ cap_watchlists_add_market (watchlist_id="...", epic="BTCUSD", confirm=true)

You: "Show markets in watchlist [id]"
→ cap_watchlists_get (watchlist_id="...")
```

---

## Safety & Risk Management

### Built-in Safety Layers

**Layer 1: Trading Disabled by Default**
- `CAP_ALLOW_TRADING=false` blocks all trade execution
- Must explicitly enable in configuration

**Layer 2: Epic Allowlist**
- `CAP_ALLOWED_EPICS` whitelist (empty = block all)
- Only listed EPICs can be traded
- Case-insensitive matching

**Layer 3: Size Limits**
- `CAP_MAX_POSITION_SIZE` (default: 1.0)
- `CAP_MAX_WORKING_ORDER_SIZE` (default: 1.0)
- Enforced during preview

**Layer 4: Position Limits**
- `CAP_MAX_OPEN_POSITIONS` (default: 3)
- `CAP_MAX_ORDERS_PER_DAY` (default: 20)
- Resets daily at midnight UTC

**Layer 5: Explicit Confirmation**
- `CAP_REQUIRE_EXPLICIT_CONFIRM=true` requires `confirm=true` parameter
- LLM must explicitly set flag, can't assume

**Layer 6: Two-Phase Execution**
- Preview validates everything (no side effects)
- Execute re-checks + requires preview_id
- Preview expires after 2 minutes

**Layer 7: Dry-Run Mode**
- `CAP_DRY_RUN=true` blocks ALL execution
- Preview still works for testing validation logic

### Best Practices

1. **Start with Demo**
   - Test extensively on demo account
   - Verify risk controls work as expected

2. **Gradual Enablement**
   - Start with trading disabled
   - Enable with strict allowlist (1-2 EPICs)
   - Use small position sizes
   - Monitor for 1-2 days before expanding

3. **Use Allowlist**
   - Never set `CAP_ALLOWED_EPICS` to "*" or empty when trading enabled
   - List only EPICs you understand and want to trade
   - Review weekly

4. **Set Conservative Limits**
   - Start with CAP_MAX_POSITION_SIZE=0.1
   - Limit daily orders (CAP_MAX_ORDERS_PER_DAY=5)
   - Keep CAP_MAX_OPEN_POSITIONS low (1-2)

5. **Monitor Activity**
   - Check positions daily: `cap_trade_positions_list`
   - Review activity: `cap_account_history_activity`
   - Watch for unexpected behavior

6. **Never Share Credentials**
   - Keep .env file secure (already in .gitignore)
   - Don't commit API keys to version control
   - Rotate keys periodically

---

## Troubleshooting

### "Session expired" errors

**Solution:**
```
Call cap_session_login to refresh session
Sessions expire after 10 minutes of inactivity
```

### "Trading disabled" error

**Solution:**
```bash
# Edit .env
CAP_ALLOW_TRADING=true
CAP_ALLOWED_EPICS=EPIC1,EPIC2

# Restart MCP client
```

### "Epic not allowed" error

**Solution:**
```bash
# Add EPIC to allowlist in .env
CAP_ALLOWED_EPICS=SILVER,GOLD,BTCUSD

# Restart MCP client
```

### "Confirm required" error

**Solution:**
```
Add confirm=true to the tool call
This is a safety feature requiring explicit confirmation
```

### "Preview expired" error

**Solution:**
```
Previews expire after 2 minutes
Create a new preview before executing
```

### "Rate limited" error

**Solution:**
```
Server enforces broker rate limits:
- Global: 10 req/s
- Session: 1 req/s
- Trading: 1 req per 0.1s

Wait a few seconds and retry
```

### Server won't start

**Check:**
1. Virtual environment activated
2. Dependencies installed: `pip install -e ".[dev]"`
3. .env file exists with required variables
4. Python 3.10+ installed: `python --version`

**View logs:**
```bash
# Set debug logging in .env
CAP_LOG_LEVEL=DEBUG

# Run server directly to see output
python -m capital_mcp.server
```

### Claude Desktop doesn't show tools

**Check:**
1. Config file path correct
2. Python path is absolute (not relative)
3. Python path points to venv Python: `which python`
4. Environment variables quoted in JSON
5. Claude Desktop restarted after config change

**Verify config:**
```bash
# macOS
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Check for syntax errors (must be valid JSON)
python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Connection refused / timeout

**Check:**
1. Capital.com API status: https://status.capital.com/
2. Network connectivity
3. Firewall not blocking HTTPS
4. API key valid and not expired
5. 2FA enabled on account

---

## Advanced Usage

### Custom Rate Limits

Edit `capital_mcp/rate_limit.py` to adjust:
- Global limit (default: 10 req/s)
- Session limit (default: 1 req/s)
- Trading limit (default: 10 req/s = 1 per 0.1s)

### Logging

```bash
# Enable debug logging
CAP_LOG_LEVEL=DEBUG

# View logs
python -m capital_mcp.server 2>&1 | tee capital_mcp.log
```

### Multiple Accounts

Configure separate servers for each account:
```json
{
  "mcpServers": {
    "capital-demo": {
      "command": "...",
      "env": {"CAP_ENV": "demo", ...}
    },
    "capital-live": {
      "command": "...",
      "env": {"CAP_ENV": "live", ...}
    }
  }
}
```

---

## Support & Resources

- **Full Specification**: [doc/capitalcom_mcp_spec.md](doc/capitalcom_mcp_spec.md)
- **Capital.com API Docs**: https://open-api.capital.com/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Issues**: https://github.com/capital-com-sv/capital-api-postman/issues

---

## Disclaimer

This software is provided "as is" for educational and engineering purposes. Trading financial instruments involves substantial risk of loss. The authors assume no responsibility for any financial losses incurred through use of this software. Always test thoroughly on Demo accounts before considering live trading. Past performance does not guarantee future results.
