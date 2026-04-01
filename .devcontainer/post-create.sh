#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r mcp-server/requirements.txt

echo "=== Installing Playwright Chromium + system deps ==="
playwright install --with-deps chromium

echo "=== Setting browser-profile permissions ==="
mkdir -p mcp-server/browser-profile
chmod 700 mcp-server/browser-profile

echo "=== Installing Ollama (local LLM runtime) ==="
if ! command -v ollama &>/dev/null; then
    apt-get update && apt-get install -y zstd
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "=== Pulling Qwen 2.5 14B model (9 GB — may take a while) ==="
ollama serve &>/dev/null &
sleep 2
ollama pull qwen2.5:14b || echo "WARNING: Model pull failed. Run 'ollama pull qwen2.5:14b' manually."

echo "=== Dev container ready ==="
echo "1. Run 'streamlit run mcp-server/frontend.py' for the web UI"
echo "2. Or use Claude Code with the MCP server (see README)"
echo "3. First time: authenticate with LinkedIn via setup_session tool"
