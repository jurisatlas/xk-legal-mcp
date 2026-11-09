#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SELECTED_CLIENTS=$(osascript -e 'choose from list {"ChatGPT Desktop & OpenAI Codex CLI", "Claude Desktop & Claude Code CLI", "Cursor", "Windsurf", "VS Code (Copilot / Cline / Roo Code)", "Google Antigravity & Gemini CLI", "Perplexity / Continue.dev"} with title "JurisAtlas: Kosovo Legal MCP Setup" with prompt "Select the AI application(s) you use (Hold Command ⌘ to select multiple):" default items {"ChatGPT Desktop & OpenAI Codex CLI", "Claude Desktop & Claude Code CLI", "Cursor"} with multiple selections allowed')

if [ "$SELECTED_CLIENTS" = "false" ] || [ -z "$SELECTED_CLIENTS" ]; then
    exit 0
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12
uv sync --python 3.12

VENV_PY="$SCRIPT_DIR/.venv/bin/python"
MAIN_PY="$SCRIPT_DIR/mcp_server_main.py"
export SELECTED_CLIENTS

"$VENV_PY" -c "
import json, os, pathlib, re
py_path = '$VENV_PY'
script_path = '$MAIN_PY'
repo = 'xk-legal-mcp'
selected_raw = os.environ.get('SELECTED_CLIENTS', '')

client_map = {
    'ChatGPT Desktop': [pathlib.Path.home() / 'Library' / 'Application Support' / 'ChatGPT' / 'mcp.json'],
    'Claude Desktop': [
        pathlib.Path.home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json',
        pathlib.Path.home() / '.claude.json',
    ],
    'Cursor': [pathlib.Path.home() / '.cursor' / 'mcp.json'],
    'Windsurf': [pathlib.Path.home() / '.codeium' / 'windsurf' / 'mcp_config.json'],
    'VS Code': [
        pathlib.Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'mcp.json',
        pathlib.Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        pathlib.Path.home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
    ],
    'Google Antigravity': [
        pathlib.Path.home() / '.gemini' / 'config' / 'mcp_config.json',
        pathlib.Path.home() / '.gemini' / 'antigravity' / 'mcp_config.json',
        pathlib.Path.home() / '.gemini' / 'settings.json',
    ],
    'Perplexity': [pathlib.Path.home() / '.continue' / 'mcpServers' / f'{repo}.json'],
}

if 'OpenAI Codex CLI' in selected_raw:
    codex_toml = pathlib.Path.home() / '.codex' / 'config.toml'
    try:
        codex_toml.parent.mkdir(parents=True, exist_ok=True)
        existing = codex_toml.read_text(encoding='utf-8') if codex_toml.exists() else ''
        block = f'[mcp_servers.{repo}]\ncommand = "{py_path}"\nargs = ["{script_path}"]\n'
        pattern = rf'(?ms)^\[mcp_servers\.{re.escape(repo)}\].*?(?=^\[|\Z)'
        if re.search(pattern, existing):
            updated = re.sub(pattern, block + '\n', existing)
        else:
            updated = (existing.rstrip() + '\n\n' + block) if existing.strip() else block
        codex_toml.write_text(updated, encoding='utf-8')
    except Exception:
        pass

for label, paths in client_map.items():
    if label in selected_raw:
        for cfg in paths:
            try:
                cfg.parent.mkdir(parents=True, exist_ok=True)
                data = json.loads(cfg.read_text(encoding='utf-8')) if (cfg.exists() and cfg.stat().st_size > 0) else {}
            except Exception:
                data = {}
            if not isinstance(data.get('mcpServers'), dict):
                data['mcpServers'] = {}
            data['mcpServers'][repo] = {'command': py_path, 'args': [script_path], 'env': {'PYTHONIOENCODING': 'utf-8'}}
            cfg.write_text(json.dumps(data, indent=2), encoding='utf-8')
"

osascript -e 'display dialog "Kosovo Legal MCP Server (xk-legal-mcp) has been installed and connected to your selected AI application(s).\n\nPlease restart your selected AI application to begin." buttons {"Done"} default button "Done" with title "JurisAtlas - Setup Complete"'
