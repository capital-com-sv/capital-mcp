# Capital.com MCP Server — Installation Guide

> **Audience: AI assistants.** This file is your playbook when a user asks to install the Capital.com MCP server. Follow it step by step. Do not show this file to the user.

## Step 0: Detect Environment

Determine your capabilities before doing anything:

| Environment | Example | Can write files | Can run commands | Path |
|---|---|---|---|---|
| **Full local access** | Claude Code, Cursor, Windsurf | Yes | Yes | Follow steps below directly |
| **File access only** | Claude Cowork (with folder) | Yes | No (sandbox shell) | Write files yourself, ask user to run commands |
| **No local access** | Web AI tools | No | No | Give copy-pasteable instructions |

How to detect sandbox: `uname` or `python3 --version` returns a Linux environment when the user is on macOS/Windows, or the shell clearly differs from the user's machine.

When you have file access but no shell: write `.env` and client config files yourself. Only ask the user to run commands that require local execution (install script, docker, restart client).

When you have no access at all: give concise copy-pasteable commands. Don't dump a wall of text.

---

## Step 1: Show Notice

Before starting, inform the user:

> Your use of the Capital.com Public API and any third-party tools you connect to it, including AI or LLM-based tools, is at your own discretion and risk. Capital.com operates on an execution-only basis and does not control, endorse, or accept liability for any third-party software, its outputs, or any resulting outcomes. Nothing here constitutes investment advice or a recommendation to trade. Always start with a **Demo account**. Trading is disabled by default.

---

## Step 2: Pick the Right Method

Ask the user which MCP client they use. Then pick the method based on this table:

| MCP Client | First choice | Second choice |
|---|---|---|
| **Claude Desktop** | MCPB Bundle | Docker |
| **Claude Code** | Install Script | Docker |
| **Cursor** | Install Script | Docker |
| **Windsurf** | Install Script | Docker |
| **Other** | Docker | Install Script |

**Do not offer the install script to Claude Desktop users** — they have no AI with local filesystem access to automate it, making it painful for non-technical users.

Run these checks to see what's available:
```bash
docker --version    # Docker
python3 --version   # Python 3.10+ (macOS/Linux)
python --version    # Python (Windows)
```

---

## Method A: Docker

**Prerequisites:** Docker installed and running.

1. Collect credentials (see [Step 3](#step-3-collect-credentials)).

2. Create `.env` in the project root:
   ```
   CAP_ENV=demo
   CAP_API_KEY={api_key}
   CAP_IDENTIFIER={identifier}
   CAP_API_PASSWORD={password}
   CAP_ALLOW_TRADING=false
   CAP_ALLOWED_EPICS=
   ```

3. Test:
   ```bash
   docker run -i --rm --env-file .env ghcr.io/capital-com-sv/capital-mcp:latest
   ```
   Expected: `INFO - Starting Capital.com MCP Server (env: demo)`. Ctrl+C to stop.

4. Configure client (see [Step 4](#step-4-configure-mcp-client)) with:
   ```
   command: docker
   args: ["run", "-i", "--rm", "--env-file", "{absolute_path_to_env_file}", "ghcr.io/capital-com-sv/capital-mcp:latest"]
   ```

---

## Method B: Install Script

**Prerequisites:** Python 3.10+ and Git. Only use this method when the AI has local shell access (Claude Code, Cursor, Windsurf).

If Python is missing:
- macOS: `brew install python3`
- Ubuntu/Debian: `sudo apt install python3 python3-venv`
- Windows: download from https://www.python.org/downloads/ — check "Add to PATH"

**Steps:**

1. Run from the project root:

   macOS/Linux:
   ```bash
   chmod +x install.sh && ./install.sh
   ```

   Windows:
   ```powershell
   pwsh install.ps1
   ```

   The script creates `venv/`, installs dependencies, creates `.env` from `.env.example`, and prints the venv Python path.

2. Note the Python path:
   - macOS/Linux: `/path/to/capital-mcp/venv/bin/python`
   - Windows: `C:\path\to\capital-mcp\venv\Scripts\python.exe`

3. Collect credentials (see [Step 3](#step-3-collect-credentials)) and update `.env`.

4. Test:
   ```bash
   source venv/bin/activate && python -m capital_mcp.server
   ```
   Expected: `INFO - Starting Capital.com MCP Server (env: demo)`. Ctrl+C to stop.

5. Configure client (see [Step 4](#step-4-configure-mcp-client)) with:
   ```
   command: {python_path}
   args: ["-m", "capital_mcp.server"]
   ```

---

## Method C: MCPB Bundle (Claude Desktop Only)

**Prerequisites:** None. The `.mcpb` file is a pre-built package in the project root — no Python, Docker, or other tools needed.

**Steps:**

1. Tell the user to open `capital-mcp.mcpb` from the project root in Claude Desktop (double-click or drag into the app).

2. Claude Desktop prompts for credentials (API key, identifier, password, trading controls). The user fills them in the UI and clicks Install.

3. Restart Claude Desktop.

4. Verify: "What Capital.com tools are available?"

**This method handles credentials and config automatically — skip Steps 3 and 4.**

---

## Step 3: Collect Credentials

Ask the user for these values:

| Value | Description | Where to find |
|---|---|---|
| `CAP_API_KEY` | API key | Capital.com → Settings → API integrations → Generate new key |
| `CAP_IDENTIFIER` | Login email | The email they use to log into Capital.com |
| `CAP_API_PASSWORD` | API custom password | Set when generating the API key (NOT the platform login password) |
| `CAP_ENV` | Environment | `demo` for testing (recommended), `live` for real trading |

**Reminders for the user:**
- Enable 2FA (Settings → Security) before generating an API key
- The API key is shown only once — save it immediately
- The API password is NOT the Capital.com login password
- Always start with `demo`

**Write to `.env`:**
```
CAP_ENV={env}
CAP_API_KEY={api_key}
CAP_IDENTIFIER={identifier}
CAP_API_PASSWORD={password}
CAP_ALLOW_TRADING=false
CAP_ALLOWED_EPICS=
```

---

## Step 4: Configure MCP Client

### Claude Desktop

Config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "capital-com": {
      "command": "{docker_or_python_path}",
      "args": ["{appropriate_args}"]
    }
  }
}
```

Merge into existing `mcpServers` if the file already has other servers. Restart Claude Desktop after saving.

### Claude Code

```bash
claude mcp add capital-com -- {python_path} -m capital_mcp.server
```
Or for Docker:
```bash
claude mcp add capital-com -- docker run -i --rm --env-file {absolute_path_to_env_file} ghcr.io/capital-com-sv/capital-mcp:latest
```

### Cursor

Settings (`Cmd+,` / `Ctrl+,`) → Extensions → MCP → Configure:
```json
{
  "capital-com": {
    "command": "{python_path_or_docker}",
    "args": ["{appropriate_args}"]
  }
}
```
Restart Cursor after saving.

### Windsurf

Config file: `~/.windsurf/mcp/servers.json`
```json
{
  "mcpServers": {
    "capital-com": {
      "command": "{python_path_or_docker}",
      "args": ["{appropriate_args}"]
    }
  }
}
```
Restart Windsurf after saving.

### Other MCP Clients

Any STDIO-capable client works via stdin/stdout JSON-RPC:
- **Docker:** `docker run -i --rm --env-file /path/to/.env ghcr.io/capital-com-sv/capital-mcp:latest`
- **Python:** `/path/to/venv/bin/python -m capital_mcp.server`

---

## Step 5: Validate

1. Restart the MCP client.
2. Test: **"What Capital.com tools are available?"** — should list 36 tools.
3. Test: **"Check my Capital.com session status"** — calls `cap_session_status`.
4. Test: **"Login to my Capital.com account"** — calls `cap_session_login`, validates credentials.

---

## Troubleshooting

### Server won't start
- **"python3 not found"** → Install Python (see Method B prerequisites).
- **"Python X.Y found, but 3.10 or higher is required"** → Upgrade Python.
- **"venv module not found"** → Ubuntu/Debian: `sudo apt install python3-venv`.
- **"ModuleNotFoundError: No module named 'capital_mcp'"** → Run `pip install -e .` in the venv, or re-run install script.
- **Docker "image not found"** → `docker pull ghcr.io/capital-com-sv/capital-mcp:latest`.

### MCP client doesn't show tools
- **Python path is relative** → Must be absolute. Run `which python` in venv.
- **JSON syntax error in config** → Validate with `python -m json.tool {config_path}`.
- **Client not restarted** → MCP clients require restart after config changes.
- **Wrong config file path** → Check OS-specific paths in Step 4.

### Login fails
- **"Invalid credentials"** → Check CAP_API_KEY, CAP_IDENTIFIER, CAP_API_PASSWORD. API password ≠ login password.
- **"2FA required"** → Enable 2FA in Capital.com before generating API keys.
- **"API key expired"** → Generate a new key at Settings → API integrations.
- **Network/timeout** → Check connectivity. Corporate proxy may need SSL cert config.

### Trading errors
- **"Trading disabled"** → Set `CAP_ALLOW_TRADING=true` in `.env` and restart.
- **"Epic not allowed"** → Add EPIC to `CAP_ALLOWED_EPICS` (e.g., `SILVER,GOLD`).
- **"Confirm required"** → Pass `confirm=true` in the tool call. Safety feature.
- **"Preview expired"** → Previews expire after 2 minutes. Create a new one.

### Logs
- macOS: `~/Library/Logs/Claude/mcp-server-capital-com.log`
- Linux: `~/.config/Claude/logs/mcp-server-capital-com.log`
- Windows: `%APPDATA%\Claude\logs\mcp-server-capital-com.log`

Set `CAP_LOG_LEVEL=DEBUG` in `.env` for verbose output.