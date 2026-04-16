# Capital.com MCP Server - Installation Script (Windows)

$ErrorActionPreference = "Stop"

Write-Host "============================================"
Write-Host "Capital.com MCP Server - Installation"
Write-Host "============================================"
Write-Host ""

# Check Python version
Write-Host "Checking Python version..."
try {
    $pythonVersion = & python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
} catch {
    Write-Host "Error: python not found. Please install Python 3.10 or higher from https://www.python.org/downloads/"
    exit 1
}

if (-not $pythonVersion) {
    Write-Host "Error: python not found. Please install Python 3.10 or higher from https://www.python.org/downloads/"
    exit 1
}

$required = [version]"3.10"
$current = [version]$pythonVersion

if ($current -lt $required) {
    Write-Host "Error: Python $pythonVersion found, but $required or higher is required."
    exit 1
}

Write-Host "OK: Python $pythonVersion found"

# Check venv module is available
try {
    & python -m venv --help 2>$null | Out-Null
} catch {
    Write-Host "Error: Python venv module not found."
    Write-Host "Reinstall Python from https://www.python.org/downloads/ and ensure 'Add to PATH' is checked."
    exit 1
}
Write-Host ""

# Create virtual environment
Write-Host "Creating virtual environment..."
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. Skipping..."
} else {
    & python -m venv venv
    Write-Host "OK: Virtual environment created"
}
Write-Host ""

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# ============================================================
# SSL / Corporate Proxy (optional)
# ============================================================
# If you are behind a corporate proxy (e.g. Netskope, Zscaler)
# that uses custom CA certificates, uncomment and set the path
# to your certificate bundle below:
#
# $env:PIP_CERT = "C:\path\to\your\ca-bundle.pem"
# $env:REQUESTS_CA_BUNDLE = $env:PIP_CERT
# $env:SSL_CERT_FILE = $env:PIP_CERT
# ============================================================

# Upgrade pip
Write-Host "Upgrading pip..."
& python -m pip install --quiet --upgrade pip
Write-Host "OK: pip upgraded"
Write-Host ""

# Install dependencies
Write-Host "Installing dependencies..."
& pip install --quiet -e ".[dev]"
Write-Host "OK: Dependencies installed"
Write-Host ""

# Create .env file if it doesn't exist
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "Creating .env file from template..."
        Copy-Item ".env.example" ".env"
        Write-Host "OK: .env file created"
        Write-Host ""
        Write-Host "IMPORTANT: Edit .env and add your Capital.com credentials:"
        Write-Host "   - CAP_API_KEY"
        Write-Host "   - CAP_IDENTIFIER"
        Write-Host "   - CAP_API_PASSWORD"
        Write-Host ""
    }
} else {
    Write-Host ".env file already exists. Skipping..."
    Write-Host ""
}

# Verify installation
Write-Host "Verifying installation..."
try {
    & python -c "import capital_mcp" 2>$null
    Write-Host "OK: Installation successful!"
} catch {
    Write-Host "Error: Installation verification failed"
    exit 1
}
Write-Host ""

# Get Python path
$pythonPath = (Get-Command python).Source

Write-Host "============================================"
Write-Host "Installation Complete!"
Write-Host "============================================"
Write-Host ""
Write-Host "Python path (use this in MCP client config):"
Write-Host "  $pythonPath"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit .env with your Capital.com credentials"
Write-Host "  2. Configure your MCP client with the JSON below"
Write-Host "  3. Restart your MCP client"
Write-Host ""
Write-Host "--- Claude Desktop / Cursor / Codex config ---"
Write-Host ""
Write-Host @"
{
  "mcpServers": {
    "capital-com": {
      "command": "$($pythonPath -replace '\\', '\\\\')",
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
"@
Write-Host ""
Write-Host "--- Claude Code config ---"
Write-Host ""
Write-Host "claude mcp add capital-com -- $pythonPath -m capital_mcp.server"
Write-Host ""
Write-Host "For detailed instructions, see README.md"
Write-Host ""
