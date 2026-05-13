#!/bin/bash
# Capital.com MCP Server - Installation Script (Mac/Linux)

set -e

echo "============================================"
echo "Capital.com MCP Server - Installation"
echo "============================================"
echo

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3.10 or higher." >&2
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [[ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]]; then
    echo "Error: Python $PYTHON_VERSION found, but $REQUIRED_VERSION or higher is required." >&2
    exit 1
fi

echo "OK: Python $PYTHON_VERSION found"

# Check venv module is available
if ! python3 -m venv --help &> /dev/null; then
    echo "Error: Python venv module not found." >&2
    echo "On Ubuntu/Debian, install it with: sudo apt install python3-venv" >&2
    echo "On macOS, reinstall Python with: brew install python3" >&2
    exit 1
fi
echo

# Create virtual environment
echo "Creating virtual environment..."
if [[ -d "venv" ]]; then
    echo "Virtual environment already exists. Skipping..."
else
    python3 -m venv venv
    echo "OK: Virtual environment created"
fi
echo

# Activate virtual environment
source venv/bin/activate

# ============================================================
# SSL / Corporate Proxy (optional)
# ============================================================
# If you are behind a corporate proxy (e.g. Netskope, Zscaler)
# that uses custom CA certificates, uncomment and set the path
# to your certificate bundle below:
#
# export PIP_CERT="/path/to/your/ca-bundle.pem"
# export REQUESTS_CA_BUNDLE="$PIP_CERT"
# export SSL_CERT_FILE="$PIP_CERT"
# ============================================================

# Upgrade pip
echo "Upgrading pip..."
pip install --quiet --upgrade pip
echo "OK: pip upgraded"
echo

# Install dependencies
echo "Installing dependencies..."
pip install --quiet -e ".[dev]"
echo "OK: Dependencies installed"
echo

# Create .env file if it doesn't exist
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        echo "Creating .env file from template..."
        cp .env.example .env
        echo "OK: .env file created"
        echo
        echo "IMPORTANT: Edit .env and add your Capital.com credentials:"
        echo "   - CAP_API_KEY"
        echo "   - CAP_IDENTIFIER"
        echo "   - CAP_API_PASSWORD"
        echo
    fi
else
    echo ".env file already exists. Skipping..."
    echo
fi

# Verify installation
echo "Verifying installation..."
if python -c "import capital_mcp" 2>/dev/null; then
    echo "OK: Installation successful!"
else
    echo "Error: Installation verification failed" >&2
    exit 1
fi
echo

# Get Python path
PYTHON_PATH=$(which python)

echo "============================================"
echo "Installation Complete!"
echo "============================================"
echo
echo "Python path (use this in MCP client config):"
echo "  $PYTHON_PATH"
echo
echo "Next steps:"
echo "  1. Edit .env with your Capital.com credentials"
echo "  2. Configure your MCP client with the JSON below"
echo "  3. Restart your MCP client"
echo
echo "--- Claude Desktop / Cursor / Codex config ---"
echo
cat <<EOF
{
  "mcpServers": {
    "capital-com": {
      "command": "$PYTHON_PATH",
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
EOF
echo
echo "--- Claude Code config ---"
echo
cat <<EOF
claude mcp add capital-com -- $PYTHON_PATH -m capital_mcp.server
EOF
echo
echo "For detailed instructions, see README.md"
echo
