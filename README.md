# Capital.com MCP Server

Model Context Protocol (MCP) server for Capital.com Open API - enabling safe, LLM-driven trading operations.

> Your use of the Capital.com Public API and any third-party tools you connect to it, including AI or LLM-based tools, is at your own discretion and risk. Capital.com operates on an execution-only basis and does not control, endorse, or accept liability for any third-party software, its outputs, or any resulting outcomes. Nothing on this page constitutes investment advice or a recommendation to trade. You are solely responsible for all trading decisions, configurations, and automated activity on your account, and must ensure your use complies with Capital.com's Terms and Conditions, Electronic Trading Terms, and all applicable laws in your jurisdiction. [Read full disclaimer](#disclaimer--use-of-capitalcom-public-api-with-third-party-tools)

## ⚠️ Important Safety Notice

- Always start with a **Demo account** before considering live trading
- Trading is **disabled by default** and requires explicit configuration
- All trade operations require **two-phase execution** (preview → confirm → execute)
- Built-in risk controls: allowlists, size limits, daily order caps

## Quick Start Guide

### Step 1: Get Capital.com API Credentials

1. **Create Account**: Go to [capital.com/trading/signup](https://capital.com/trading/signup)
   - Choose **Demo** account for testing (recommended)
   - Verify your email

2. **Enable 2FA**: Settings > Security > Two-Factor Authentication
   - Required before generating API keys

3. **Generate API Key**: Settings > API integrations > Generate new key
   - Set a label (e.g., "MCP Server")
   - **Set a custom password** (this is NOT your platform password)
   - Save the API key shown (displayed only once!)
   - Note: API keys are trading-capable; Capital.com doesn't offer read-only keys

### Step 2: Install & Configure

**Prerequisites:** Python 3.10+ and Git must be installed.
- macOS: `brew install python3 git`
- Ubuntu/Debian: `sudo apt install python3 python3-venv git`
- Windows: [python.org](https://www.python.org/downloads/) (check "Add to PATH" during install) + [git-scm.com](https://git-scm.com/)

**Mac/Linux:**
```bash
cd /path/to/capital-mcp
./install.sh
```

**Windows (PowerShell):**
```powershell
cd C:\path\to\capital-mcp
pwsh install.ps1
```

The install script will create a virtual environment, install dependencies, and print the MCP client configuration for you.

Edit `.env` with your credentials:

```bash
# Required
CAP_ENV=demo
CAP_API_KEY=your_generated_api_key_here
CAP_IDENTIFIER=your_email@example.com
CAP_API_PASSWORD=your_custom_api_password

# Safety (keep trading disabled until ready)
CAP_ALLOW_TRADING=false
CAP_ALLOWED_EPICS=

# Optional: enable later for real trading
# CAP_ALLOW_TRADING=true
# CAP_ALLOWED_EPICS=SILVER,GOLD,BTCUSD
```

### Step 3: Test Server Locally

**Mac/Linux:**
```bash
source venv/bin/activate
python -m capital_mcp.server
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
python -m capital_mcp.server
```

You should see:
```
INFO - Starting Capital.com MCP Server (env: demo)
INFO - Trading enabled: False
```

Press Ctrl+C to stop.

### Troubleshooting: Check Logs

If you encounter issues when using the MCP server with Claude Desktop or other clients, check the log files:

**macOS**:
```bash
# View MCP server logs
tail -f ~/Library/Logs/Claude/mcp-server-capital-com.log

# Search for errors
grep -i error ~/Library/Logs/Claude/mcp-server-capital-com.log
```

**Linux**:
```bash
tail -f ~/.config/Claude/logs/mcp-server-capital-com.log
```

**Windows**:
```powershell
Get-Content $env:APPDATA\Claude\logs\mcp-server-capital-com.log -Wait
```

---

## Integration

> **Note:** Replace `/path/to/capital-mcp/venv/bin/python` with your actual venv Python path. The install script prints this for you. On Windows, use `C:\path\to\capital-mcp\venv\Scripts\python.exe`.

### Claude Desktop

#### macOS/Linux

Config location: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux)

```json
{
  "mcpServers": {
    "capital-com": {
      "command": "/path/to/capital-mcp/venv/bin/python",
      "args": ["-m", "capital_mcp.server"],
      "env": {
        "CAP_ENV": "demo",
        "CAP_API_KEY": "your_api_key_here",
        "CAP_IDENTIFIER": "your_email@example.com",
        "CAP_API_PASSWORD": "your_custom_password",
        "CAP_ALLOW_TRADING": "false",
        "CAP_ALLOWED_EPICS": ""
      }
    }
  }
}
```

Restart Claude Desktop. Verify by typing: "What Capital.com tools are available?"

#### Windows

Config location: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "capital-com": {
      "command": "C:\\path\\to\\capital-mcp\\venv\\Scripts\\python.exe",
      "args": ["-m", "capital_mcp.server"],
      "env": {
        "CAP_ENV": "demo",
        "CAP_API_KEY": "your_api_key_here",
        "CAP_IDENTIFIER": "your_email@example.com",
        "CAP_API_PASSWORD": "your_custom_password",
        "CAP_ALLOW_TRADING": "false",
        "CAP_ALLOWED_EPICS": ""
      }
    }
  }
}
```

Restart Claude Desktop.

### Claude Code

```bash
claude mcp add capital-com -- /path/to/capital-mcp/venv/bin/python -m capital_mcp.server
```

### Cursor IDE

Open Settings (`Cmd+,` / `Ctrl+,`) > Extensions > MCP > Configure. Add:

```json
{
  "capital-com": {
    "command": "/path/to/capital-mcp/venv/bin/python",
    "args": ["-m", "capital_mcp.server"],
    "env": {
      "CAP_ENV": "demo",
      "CAP_API_KEY": "your_api_key_here",
      "CAP_IDENTIFIER": "your_email@example.com",
      "CAP_API_PASSWORD": "your_custom_password",
      "CAP_ALLOW_TRADING": "false"
    }
  }
}
```

Restart Cursor.

### Codex

Settings > MCP Servers > Add server. Use the same command, args, and env vars as above.

### Windsurf

Create/edit `~/.windsurf/mcp/servers.json`:

```json
{
  "mcpServers": {
    "capital-com": {
      "command": "/path/to/capital-mcp/venv/bin/python",
      "args": ["-m", "capital_mcp.server"],
      "env": {
        "CAP_ENV": "demo",
        "CAP_API_KEY": "your_api_key_here",
        "CAP_IDENTIFIER": "your_email@example.com",
        "CAP_API_PASSWORD": "your_custom_password"
      }
    }
  }
}
```

Restart Windsurf.

### Custom MCP Clients

Any STDIO-capable MCP client works. Example with Node.js:

```typescript
import { spawn } from 'child_process';

const server = spawn('/path/to/venv/bin/python', ['-m', 'capital_mcp.server'], {
  env: {
    ...process.env,
    CAP_ENV: 'demo',
    CAP_API_KEY: 'your_key',
    CAP_IDENTIFIER: 'your_email',
    CAP_API_PASSWORD: 'your_password',
    CAP_ALLOW_TRADING: 'false'
  }
});

// Communicate via STDIO (JSON-RPC)
// Read from server.stdout, write to server.stdin
```

## Usage Examples

### Example Conversation with Claude Desktop

```
You: "Check my Capital.com session status"

Claude: I'll check your session status.
[Calls cap_session_status]
Response: {"ok": true, "data": {"env": "demo", "logged_in": false, ...}}

You're not currently logged in to the demo environment.

---

You: "Login to my Capital.com account"

Claude: I'll log you in.
[Calls cap_session_login]
Success! Logged in to account ID: ABC123

---

You: "Search for Bitcoin markets"

Claude: Searching for Bitcoin...
[Calls cap_market_search with search_term="Bitcoin"]
Found 5 markets:
- BTCUSD: Bitcoin vs US Dollar
- BTCEUR: Bitcoin vs Euro
- BTCGBP: Bitcoin vs British Pound
...

---

You: "Show me current positions"

Claude: Let me check your positions.
[Calls cap_trade_positions_list]
You have no open positions.

---

You: "Preview buying 1.0 SILVER"

Claude: I'll preview this trade. Note: Trading is currently DISABLED.
[Calls cap_trade_preview_position]
Preview failed: Trading is disabled (CAP_ALLOW_TRADING=false)

To enable trading, update your .env file:
CAP_ALLOW_TRADING=true
CAP_ALLOWED_EPICS=SILVER
```

### Safe Trading Workflow (When Trading Enabled)

```
1. Preview the trade (validates everything, no side effects):
   "Preview buying 2.0 SILVER with stop at 24.50"
   → Returns preview_id

2. Review the preview results:
   - Normalized size (rounded to broker increments)
   - Risk checks (allowlist, size limits, daily limits)
   - Estimated entry price

3. Execute ONLY if all checks pass:
   "Execute position with preview_id [id], confirm=true"
   → Creates real position
   → Returns deal_reference
   → Polls for broker confirmation

4. Monitor:
   "Show my positions"
   "Close position [deal_id] with confirm=true"
```

## Environment Variables Reference

### Required
- `CAP_ENV` - Environment: `demo` or `live` (default: demo)
- `CAP_API_KEY` - API key from Capital.com
- `CAP_IDENTIFIER` - Login email
- `CAP_API_PASSWORD` - API key custom password

### Safety Controls (Recommended)
- `CAP_ALLOW_TRADING` - Enable trading (default: false)
- `CAP_ALLOWED_EPICS` - Comma-separated allowlist (e.g., "SILVER,GOLD,BTCUSD") or "ALL" for unrestricted
- `CAP_MAX_POSITION_SIZE` - Max position size (default: 1.0)
- `CAP_MAX_WORKING_ORDER_SIZE` - Max order size (default: 1.0)
- `CAP_MAX_OPEN_POSITIONS` - Max concurrent positions (default: 3)
- `CAP_MAX_ORDERS_PER_DAY` - Daily order limit (default: 20)
- `CAP_REQUIRE_EXPLICIT_CONFIRM` - Require confirm=true (default: true)
- `CAP_DRY_RUN` - Block all trade executions (default: false)

### Optional
- `CAP_DEFAULT_ACCOUNT_ID` - Default account after login
- `CAP_HTTP_TIMEOUT_S` - HTTP timeout (default: 15)
- `CAP_LOG_LEVEL` - Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## MCP Tools (36 implemented)

### Session (4)
- `cap_session_status` - Get session info
- `cap_session_login` - Create session
- `cap_session_ping` - Keep alive
- `cap_session_logout` - End session

### Market Data (6)
- `cap_market_search` - Search markets
- `cap_market_get` - Get market details
- `cap_market_prices` - Historical prices
- `cap_market_sentiment` - Client sentiment
- `cap_market_navigation_root` - Market categories root
- `cap_market_navigation_node` - Market categories node

### Account (6)
- `cap_account_list` - List accounts
- `cap_account_preferences_get` - Get preferences
- `cap_account_preferences_set` - Set preferences
- `cap_account_history_activity` - Activity history
- `cap_account_history_transactions` - Transaction history
- `cap_account_demo_topup` - Top up demo account

### Trading (11)
- **Read-only:**
  - `cap_trade_positions_list` - List positions
  - `cap_trade_positions_get` - Get position details
  - `cap_trade_orders_list` - List working orders
  - `cap_trade_confirm_get` - Get confirmation status
  - `cap_trade_confirm_wait` - Wait for confirmation

- **Preview (safe):**
  - `cap_trade_preview_position` - Preview position
  - `cap_trade_preview_working_order` - Preview order

- **Execute (guarded):**
  - `cap_trade_execute_position` - Execute position
  - `cap_trade_execute_working_order` - Execute order
  - `cap_trade_positions_close` - Close position
  - `cap_trade_orders_cancel` - Cancel order

### Watchlists (6)
- `cap_watchlists_list` - List watchlists
- `cap_watchlists_create` - Create watchlist
- `cap_watchlists_get` - Get watchlist
- `cap_watchlists_add_market` - Add market
- `cap_watchlists_delete` - Delete watchlist
- `cap_watchlists_remove_market` - Remove market

### Streaming (3)
- `cap_stream_prices` - Stream real-time prices (WebSocket)
- `cap_stream_alerts` - Stream price level alerts (WebSocket)
- `cap_stream_portfolio` - Stream live portfolio P&L (WebSocket)

## MCP Prompts (Workflow Templates)

MCP prompts are structured workflows that guide Claude through complex multi-step trading operations. They provide step-by-step instructions and best practices for common tasks.

### Available Prompts (4)

#### 1. `market_scan` - Market Analysis Workflow
Guides you through scanning a watchlist for trading opportunities.

**Parameters:**
- `watchlist_id` - Watchlist to scan (leave empty to list watchlists first)
- `timeframe` - Price resolution: MINUTE, MINUTE_5, HOUR, DAY (default: HOUR)
- `lookback_periods` - Number of candles to fetch: 1-1000 (default: 24)

**Workflow:**
1. Get watchlist markets
2. Fetch price data for each market
3. Technical analysis (trends, support/resistance, patterns)
4. Optional sentiment check
5. Generate opportunity summary

**Example Usage:**
- "Use the market_scan prompt to analyze my watchlist"
- "Scan my markets for trading setups"

**Real trading:**
Change your configurations to:
    CAP_ENV: 'live',
    CAP_ALLOW_TRADING: 'true'


#### 2. `trade_proposal` - Trade Planning Workflow
Guides you through creating a trade proposal with proper risk management.

**Parameters:**
- `epic` - Market to trade (required, e.g., SILVER, GOLD)
- `direction` - BUY or SELL (default: BUY)
- `thesis` - Your trading reasoning (optional)
- `risk_percent` - Risk as % of balance (default: 1.0%)

**Workflow:**
1. Fetch market details and dealing rules
2. Calculate position size based on risk %
3. Define stop loss and take profit levels
4. Preview the trade (validation only - no execution)
5. Return preview_id for potential execution

**Example Usage:**
- "Create a trade proposal for SILVER"
- "Propose a long trade on GOLD with 2% risk"

**Safety:** This prompt does NOT execute trades - it only creates previews.

#### 3. `execute_trade` - Trade Execution Workflow
Guides you through executing a previewed trade safely.

**Parameters:**
- `preview_id` - Preview ID from trade_proposal (required)

**Workflow:**
1. Verify preview_id is provided and valid
2. Re-check all risk controls
3. Execute position with broker
4. Poll for confirmation (ACCEPTED/REJECTED)
5. Report final status

**Example Usage:**
- "Execute the trade I just previewed"
- "Place the trade with preview ID abc-123"

**Safety:**
- Requires CAP_ALLOW_TRADING=true
- Requires epic in allowlist
- Preview must not be expired (2-minute TTL)
- ⚠️ **This WILL place a real trade**

#### 4. `position_review` - Portfolio Analysis Workflow
Guides you through analyzing your open positions and orders.

**Parameters:** None (analyzes all current positions)

**Workflow:**
1. Fetch all open positions
2. Fetch all working orders
3. Calculate P&L, risk, and exposure metrics
4. Identify concentration and correlation risks
5. Suggest potential adjustments (without executing)

**Example Usage:**
- "Review my current positions"
- "Analyze my portfolio exposure"

**Safety:** This is a read-only workflow - no trades are executed.

### How to Use Prompts

In Claude Desktop or other MCP clients, prompts appear as available interaction patterns. You can invoke them naturally in conversation:

```
User: "I want to scan my watchlist for opportunities"
Claude: [Invokes market_scan prompt, guides through the workflow]

User: "Create a trade plan for SILVER"
Claude: [Invokes trade_proposal prompt, designs trade with risk management]

User: "Execute that trade"
Claude: [Invokes execute_trade prompt, submits to broker]

User: "Show me my open positions"
Claude: [Invokes position_review prompt, analyzes portfolio]
```

Prompts provide structured guidance while maintaining safety controls throughout the workflow.

## MCP Resources (Read-Only Data)

MCP resources provide read-only access to server state and configuration through URI-based resources. Unlike tools (which perform actions), resources expose data that clients can read and monitor.

### Available Resources

#### 1. `cap://status` - Server Status

Real-time server and session information.

**Returns**: JSON with server health, session state, authentication status, rate limits

**Example**:
```json
{
  "server": {
    "name": "Capital.com MCP Server",
    "version": "0.1.0",
    "trading_enabled": true
  },
  "session": {
    "logged_in": true,
    "account_id": "ABC123",
    "last_used_at": "2026-01-16T10:30:00Z",
    "expires_in_s_estimate": 522
  },
  "risk": {
    "trading_enabled": true,
    "allowed_epics": ["GOLD", "SILVER"],
    "allowlist_mode": "SPECIFIC"
  },
  "rate_limits": {
    "requests_per_second": "10",
    "note": "Capital.com enforces 10 req/s limit"
  }
}
```

**Use Cases**: Monitor server health, check session status, debug authentication issues

---

#### 2. `cap://risk-policy` - Risk Policy

Comprehensive risk management configuration and safety controls.

**Returns**: JSON with all validation layers, safety features, and trading restrictions

**Example**:
```json
{
  "trading_enabled": true,
  "two_phase_execution": true,
  "description": "All trades require preview → explicit execution",
  "allowlist": {
    "mode": "SPECIFIC",
    "epics": ["GOLD", "SILVER"],
    "note": "Only markets on this list can be traded (ALL = wildcard)"
  },
  "validation_layers": [
    "1. Trading enabled check (TRADING_ENABLED env var)",
    "2. Epic allowlist check (must be in ALLOWED_EPICS)",
    "... 10 total layers ..."
  ],
  "safety_features": {
    "preview_required": true,
    "deal_reference_matching": true,
    "authentication_required": true,
    "rate_limiting": true,
    "input_validation": true
  }
}
```

**Use Cases**: Understand active safety controls, audit risk configuration, compliance documentation

---

#### 3. `cap://allowed-epics` - Trading Allowlist

Current trading allowlist configuration showing permitted markets.

**Returns**: JSON with allowlist mode, permitted epics, and configuration instructions

**Example**:
```json
{
  "mode": "SPECIFIC",
  "allowed_epics": ["GOLD", "SILVER", "BTCUSD"],
  "count": 3,
  "trading_enabled": true,
  "description": "Restricted mode: 3 specific markets allowed",
  "configuration": {
    "env_var": "ALLOWED_EPICS",
    "example": "ALLOWED_EPICS=GOLD,SILVER,BTCUSD",
    "wildcard": "ALLOWED_EPICS=ALL (allows all markets)"
  }
}
```

**Use Cases**: Check which markets are tradeable, verify allowlist configuration

---

#### 4. `cap://market-cache/{epic}` - Market Details (Dynamic)

Cached market details for a specific epic (live fetch from broker).

**Parameters**:
- `epic` - Market identifier (e.g., "GOLD", "SILVER", "CS.D.EURUSD.TODAY.IP")

**Returns**: JSON with comprehensive market information

**Authentication**: Required

**Example**: `cap://market-cache/GOLD`

```json
{
  "epic": "GOLD",
  "instrument_name": "Spot Gold",
  "instrument_type": "COMMODITIES",
  "currency": "USD",
  "snapshot": {
    "market_status": "TRADEABLE",
    "bid": 2050.50,
    "offer": 2050.75,
    "update_time": "2026-01-16T10:30:00"
  },
  "dealing": {
    "min_size": 0.1,
    "max_size": 100.0,
    "min_step": 0.1,
    "min_stop_distance": 5.0
  },
  "margin": {
    "factor": 5.0,
    "unit": "PERCENTAGE"
  },
  "opening_hours": {...},
  "cached_at": "2026-01-16T10:30:00"
}
```

**Use Cases**: Get market details, check trading rules, analyze margin requirements

---

### How to Use Resources

In Claude Desktop or other MCP clients, resources can be accessed by URI:

```
User: "Show me the server status"
Claude: [Reads cap://status resource, displays server health]

User: "What's the risk policy?"
Claude: [Reads cap://risk-policy resource, explains safety controls]

User: "Which markets can I trade?"
Claude: [Reads cap://allowed-epics resource, lists permitted epics]

User: "Show all my watchlists"
Claude: [Calls cap_watchlists_list tool, displays watchlist data]

User: "Get details for GOLD market"
Claude: [Reads cap://market-cache/GOLD resource, shows market info]
```

Resources provide a convenient way to inspect server state and configuration without running tools. For watchlist data, use the `cap_watchlists_list` and `cap_watchlists_get` tools.

## Safety Model

### Two-Phase Execution
All side-effect operations use a strict preview → execute flow:

1. **Preview**: Validate trade against broker rules + local risk policy
   - Returns `preview_id` with normalized request + risk checks
   - No side effects, read-only validation

2. **Execute**: Submit trade using `preview_id`
   - Re-runs critical checks
   - Requires `confirm=true` if `CAP_REQUIRE_EXPLICIT_CONFIRM=true`
   - Polls broker confirmation
   - Increments daily order counter

### Risk Guardrails
- **Allowlist**: Only EPICs in `CAP_ALLOWED_EPICS` can be traded
- **Size Limits**: Max position/order size enforced
- **Position Limits**: Max open positions at any time
- **Daily Limits**: Max orders per day
- **Size Normalization**: Rounds to broker min/max/increment
- **Dry-Run Mode**: Blocks all executions when enabled

## Documentation

- **Usage Guide**: [USAGE.md](USAGE.md) - Comprehensive usage guide with examples
- **Capital.com API Reference**: https://open-api.capital.com/
- **Capital.com API Postman Collection**: https://github.com/capital-com-sv/capital-api-postman

## License

MIT

## **Disclaimer — Use of Capital.com Public API with Third-Party Tools**

### Third-Party Integration

This page describes how clients may connect the Capital.com Public API to third-party software, tools, or integrations, including those powered by artificial intelligence or large language models ("LLMs"). Any such third-party software, tool, or integration is independent of Capital.com and does not form part of Capital.com's services. Capital.com does not control, develop, endorse, or accept any liability for any third-party software, its functionality, outputs, or any outcomes arising from its use. Any use of third-party tools or integrations in connection with the Capital.com Public API is entirely at your own risk. You are responsible for reviewing the terms, privacy policies, and data-handling practices of any third-party tool you choose to use.

### Use of the Public API

Your use of the Capital.com Public API is entirely at your own discretion and risk. Capital.com makes the Public API available for informational and trading purposes but does not recommend, endorse, or encourage any particular use, integration, or trading strategy. You are solely responsible for how you access and use the API, including the parameters of any orders submitted, the configuration of any connected tools or systems, and the interpretation of any data received. Capital.com accepts no liability for losses or unintended outcomes arising from your use of the API, whether accessed directly or through third-party tools. API availability, functionality, and specifications may be modified, rate-limited, suspended, or discontinued at any time without prior notice. Your use of the Public API is subject to Capital.com's Terms and Conditions and Electronic Trading Terms, which you should read carefully before using the API.

### Execution-Only Service and No Investment Advice

Capital.com provides its services on an execution-only basis. Trading financial instruments involves significant risk of loss. Nothing on this page, in the Public API, or in any third-party software or integration constitutes investment advice, a personal recommendation, or a solicitation to buy or sell any financial instrument. This includes any output, signal, suggestion, or analysis generated by AI, LLM-based, or other automated tools. All trading decisions, including any automated or algorithmic activity, are made at your own risk and remain your sole responsibility.

### Risks of Automated and Algorithmic Trading

Use of the Public API in connection with automated or algorithmic trading tools carries additional risks, including but not limited to: rapid execution of orders without human review or intervention; system errors, software failures, or connectivity issues; execution at prices materially different from those expected; and unintended or erroneous orders resulting from misconfigured tools or parameters. Capital.com is not responsible for any losses arising from such risks or from the interaction between its systems and any third-party tools. Past performance and any outputs generated by automated tools are not indicative of future results.

### Prohibited Use

Use of the Public API and any connected tools must not be used to manipulate the Capital.com platform, exploit pricing or latency, engage in market abuse, or obtain any unfair advantage. Capital.com reserves the right to restrict, suspend, or terminate API access and/or your account where it reasonably considers that such misuse has occurred or is likely to occur. Clients must not permit any third party to exercise discretionary control over their account.

### Your Responsibilities

You are responsible for ensuring that your use of the Capital.com platform, the Public API, and any third-party tools or integrations complies with Capital.com's Terms and Conditions, Electronic Trading Terms, and all applicable laws and regulations in your jurisdiction. You should carefully consider whether automated trading tools are appropriate for your circumstances, experience, and risk tolerance before using them. Capital.com strongly recommends that you test any automated tools or integrations thoroughly using a Demo account before connecting them to a live trading environment.
