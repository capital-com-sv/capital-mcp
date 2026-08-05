# Capital.com MCP Server

Model Context Protocol (MCP) server for Capital.com Open API - enabling LLM-driven access to your Capital.com trading account.

## ⚠️ Important Notice

**Your use of the Capital.com Public API and any third-party tools, including AI/LLM-based tools, is at your own risk. Capital.com is execution-only and does not endorse or take responsibility for third-party software or its outcomes. Nothing here is investment advice. You are solely responsible for your trading decisions, including any price differences arising from latency introduced by third-party tools, and must comply with applicable terms and laws.**

**Crypto Derivatives are not available to Retail clients registered with Capital Com (UK) Ltd.**

- Always start with a **Demo account** before considering live trading
- Trading is **disabled by default** and requires explicit configuration
- All trade operations require **two-phase execution** (preview → confirm → execute)
- Built-in risk controls: allowlists, size limits, daily order caps
- **Use at your own risk** - the authors assume no liability for trading losses

**For further questions/clarifications, please refer to the FAQ: https://help.capitalccuk.com/hc/en-us/articles/34503231743506-How-to-set-up-the-Capital-com-MCP-Server**

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

**AI-Guided Install:** Open this project folder in an AI-powered editor (Claude Code, Cursor, Windsurf) and ask it to install the Capital.com MCP server — it will follow [INSTALL.md](INSTALL.md) to guide you through setup, picking the best method for your environment.

You also have these manual installation options:

#### Option A: One-Click Install via MCPB Bundle (Recommended)

The repo includes a pre-built `capital-mcp.mcpb` bundle — open it in Claude Desktop and you're done, no manual config editing required.

**Steps:**

1. Clone the repo:
   ```bash
   git clone https://github.com/capital-com-sv/capital-mcp.git
   cd capital-mcp
   ```
2. Open `capital-mcp.mcpb` in Claude Desktop (double-click, or drag it into the app).
3. Claude Desktop will prompt you for credentials (API key, identifier, password) and trading controls. Fill them in and click Install.
4. Restart Claude Desktop and verify by asking: "What Capital.com tools are available?"

#### Option B: Manual Install via Script

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

# Trading controls (keep trading disabled until ready)
CAP_ALLOW_TRADING=false
CAP_ALLOWED_EPICS=

# Optional: enable later for real trading
# CAP_ALLOW_TRADING=true
# CAP_ALLOWED_EPICS=SILVER,GOLD,BTCUSD
```

#### Option C: Docker

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) must be installed.

1. Create a `.env` file with your credentials (see [.env.example](.env.example)):
   ```bash
   CAP_ENV=demo
   CAP_API_KEY=your_api_key_here
   CAP_IDENTIFIER=your_email@example.com
   CAP_API_PASSWORD=your_custom_password
   CAP_ALLOW_TRADING=false
   ```

2. Run the server:
   ```bash
   docker run -i --rm --env-file .env ghcr.io/capital-com-sv/capital-mcp:latest
   ```

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

## Client Integration

For client-specific configuration (Claude Desktop, Claude Code, Cursor, Windsurf, Codex, Docker, custom clients), see [USAGE.md — Client Integration](USAGE.md#client-integration).

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

### Trade Execution Workflow (When Trading Enabled)

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

### Risk Controls (Recommended)
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

## MCP Capabilities

**38 tools** across 6 categories, **7 workflow prompts**, and **4 read-only resources**.

| Category | Tools | Description |
|----------|-------|-------------|
| Session | 4 | Login, logout, status, keep-alive |
| Market Data | 6 | Search, details, prices, sentiment, navigation |
| Account | 6 | List accounts, preferences, activity/transaction history, demo top-up |
| Trading | 13 | Preview, execute, close positions; list/cancel/amend working orders; confirmations |
| Watchlists | 6 | Create, list, get, delete watchlists; add/remove markets |
| Streaming | 3 | Real-time prices, alerts, portfolio P&L via WebSocket |

| Prompt | Description |
|--------|-------------|
| `market_scan` | Scan a watchlist for trading conditions |
| `trade_proposal` | Plan a trade with risk-based sizing (preview only) |
| `execute_trade` | Execute a previously previewed trade |
| `position_review` | Analyze open positions and exposure (read-only) |
| `live_price_monitor` | Real-time price tracking with move alerts (WebSocket) |
| `real_time_alerts` | Conditional price level alerts (WebSocket) |
| `live_portfolio_monitor` | Live portfolio P&L dashboard (WebSocket) |

| Resource | Description |
|----------|-------------|
| `cap://status` | Server health, session state, rate limits |
| `cap://risk-policy` | Risk management config and validation layers |
| `cap://allowed-epics` | Trading allowlist configuration |
| `cap://market-cache/{epic}` | Cached market details (live fetch) |

For full details, parameters, and examples see [USAGE.md](USAGE.md).

## Trade Execution Process

### Mandatory Two-Step Execution
All side-effect operations use a strict preview → execute flow:

1. **Preview**: Validate trade against broker rules + local risk policy
   - Returns `preview_id` with normalized request + risk checks
   - No side effects, read-only validation

2. **Execute**: Submit trade using `preview_id`
   - Re-runs critical checks
   - Requires `confirm=true` if `CAP_REQUIRE_EXPLICIT_CONFIRM=true`
   - Polls broker confirmation
   - Increments daily order counter

### Risk Controls
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

## Privacy Policy

The Capital.com MCP server runs locally on your machine and communicates directly with the Capital.com Public API using credentials you supply. It does not operate as a hosted service and has no servers of its own.

**Data collection**

The MCP server does not collect or store any data. It acts as a local bridge between your AI client and the Capital.com Public API.

**Data usage and storage**

All data exchanged during a session is processed in memory on your local machine and discarded when the session ends. No data is written to disk by the MCP server. Note: Your AI client may process, log, or store data passed through it in accordance with its own privacy policy, which you should review separately.

**Third-party sharing**

The MCP server does not share data with any third party. Data flows only between your local environment and the Capital.com Public API, subject to Capital.com's own Privacy Policy.

**Data retention**

The MCP server retains no data. Session data exists only in memory for the duration of the session.

**API Credentials**

API credentials you provide are stored and managed in your local environment. You are responsible for securing them appropriately.

**Contact**

For privacy-related queries regarding your Capital.com account or how Capital.com handles your data, refer to the [Capital.com Privacy Policy](https://capital.com/privacy-policy) or contact [support@capital.com](mailto:support@capital.com).

## Disclaimer – Use of Capital.com Public API with Third-Party Tools

#### Third-Party Integration
This page describes how clients may connect the Capital.com Public API to third-party software, tools, or integrations, including those powered by artificial intelligence or large language models ('LLMs'). Any such third-party software, tool, or integration is independent of Capital.com and does not form part of Capital.com's services. Capital.com does not control, develop, endorse, or accept any liability for any third-party software, its functionality, outputs, or any outcomes arising from its use. Any use of third-party tools or integrations in connection with the Capital.com Public API is entirely at your own risk. You are responsible for reviewing the terms, privacy policies, and data-handling practices of any third-party tool you choose to use.

#### Use of the Public API
Your use of the Capital.com Public API is entirely at your own discretion and risk. Capital.com makes the Public API available for informational and trading purposes but does not recommend, endorse, or encourage any particular use, integration, or trading strategy. You are solely responsible for how you access and use the API, including the parameters of any orders submitted, the configuration of any connected tools or systems, and the interpretation of any data received. Capital.com accepts no liability for losses or unintended outcomes arising from your use of the API, whether accessed directly or through third-party tools. API availability, functionality, and specifications may be modified, rate-limited, suspended, or discontinued at any time without prior notice. Your use of the Public API is subject to Capital.com's Terms and Conditions and Electronic Trading Terms, which you should read carefully before using the API.

#### Execution-Only Service and No Investment Advice
Capital.com provides its services on an execution-only basis. Trading financial instruments involves significant risk of loss. Nothing on this page, in the Public API, or in any third-party software or integration constitutes investment advice, a personal recommendation, or a solicitation to buy or sell any financial instrument. This includes any output, signal, suggestion, or analysis generated by AI, LLM-based, or other automated tools. All trading decisions, including any automated or algorithmic activity, are made at your own risk and remain your sole responsibility. Capital.com does not control the outputs of third-party AI or LLM-based tools connected to the Public API and cannot guarantee that such tools will not generate content that could be construed as investment advice or a personal recommendation. Any such output is not provided by or on behalf of Capital.com and should not be relied upon as advice.

#### Risks of Automated and Algorithmic Trading
Use of the Public API in connection with automated or algorithmic trading tools carries additional risks, including but not limited to: rapid execution of orders without human review or intervention; system errors, software failures, or connectivity issues; execution at prices materially different from those expected; and unintended or erroneous orders resulting from misconfigured tools or parameters. Capital.com is not responsible for any losses arising from such risks or from the interaction between its systems and any third-party tools. Past performance and any outputs generated by automated tools are not indicative of future results.

Where AI or LLM-based tools are used to retrieve market data or pricing information, there may be a delay between the price communicated by the tool and the price at which any resulting order is executed. All orders placed through the Public API are executed as market orders. The execution price may therefore differ from any price displayed at the time of a request. Capital.com seeks to achieve best execution in accordance with its obligations; we do not accept liability for price differences arising from latency attributable to third-party tools or systems outside its control.

#### Prohibited Use
Use of the Public API and any connected tools must not be used to manipulate the Capital.com platform, exploit pricing or latency, engage in market abuse, or obtain any unfair advantage. Capital.com reserves the right to restrict, suspend, or terminate API access and/or your account where it reasonably considers that such misuse has occurred or is likely to occur. Clients must not permit any third party to exercise discretionary control over their account.

#### Your Responsibilities
You are responsible for ensuring that your use of the Capital.com platform, the Public API, and any third-party tools or integrations complies with Capital.com's Terms and Conditions, Electronic Trading Terms, and all applicable laws and regulations in your jurisdiction. You should carefully consider whether automated trading tools are appropriate for your circumstances, experience, and risk tolerance before using them. Capital.com strongly recommends that you test any automated tools or integrations thoroughly using a Demo account before connecting them to a live trading environment.
