# JurisAtlas Interactive AI Client Selector & Setup Wizard (Windows Forms GUI)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoName = "xk-legal-mcp"
$CountryName = "Kosovo"

$form = New-Object System.Windows.Forms.Form
$form.Text = "JurisAtlas - $CountryName Legal MCP Setup"
$form.Size = New-Object System.Drawing.Size(580, 520)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "JurisAtlas: $CountryName Legal MCP Setup"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 13.5, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$titleLabel.Location = New-Object System.Drawing.Point(25, 18)
$titleLabel.Size = New-Object System.Drawing.Size(515, 30)
$form.Controls.Add($titleLabel)

$safeBox = New-Object System.Windows.Forms.Label
$safeBox.Text = "Read-Only & Isolated Installation`r`n• Does NOT access or modify your personal files or documents.`r`n• Select the AI application(s) you use below to connect $CountryName legislation & multi-tier court decisions."
$safeBox.Font = New-Object System.Drawing.Font("Segoe UI", 9.2)
$safeBox.ForeColor = [System.Drawing.Color]::FromArgb(51, 65, 85)
$safeBox.BackColor = [System.Drawing.Color]::FromArgb(224, 242, 254)
$safeBox.BorderStyle = "FixedSingle"
$safeBox.Padding = New-Object System.Windows.Forms.Padding(10)
$safeBox.Location = New-Object System.Drawing.Point(25, 55)
$safeBox.Size = New-Object System.Drawing.Size(515, 76)
$form.Controls.Add($safeBox)

$groupBox = New-Object System.Windows.Forms.GroupBox
$groupBox.Text = "Select the AI Application(s) You Use:"
$groupBox.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$groupBox.ForeColor = [System.Drawing.Color]::FromArgb(30, 41, 59)
$groupBox.Location = New-Object System.Drawing.Point(25, 142)
$groupBox.Size = New-Object System.Drawing.Size(515, 172)
$form.Controls.Add($groupBox)

$cbCodex = New-Object System.Windows.Forms.CheckBox
$cbCodex.Text = "ChatGPT Desktop & OpenAI Codex CLI"
$cbCodex.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbCodex.Location = New-Object System.Drawing.Point(18, 26)
$cbCodex.Size = New-Object System.Drawing.Size(235, 24)
$cbCodex.Checked = $true
$groupBox.Controls.Add($cbCodex)

$cbClaude = New-Object System.Windows.Forms.CheckBox
$cbClaude.Text = "Claude Desktop & Claude Code CLI"
$cbClaude.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbClaude.Location = New-Object System.Drawing.Point(265, 26)
$cbClaude.Size = New-Object System.Drawing.Size(235, 24)
$cbClaude.Checked = $true
$groupBox.Controls.Add($cbClaude)

$cbCursor = New-Object System.Windows.Forms.CheckBox
$cbCursor.Text = "Cursor Editor"
$cbCursor.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbCursor.Location = New-Object System.Drawing.Point(18, 58)
$cbCursor.Size = New-Object System.Drawing.Size(235, 24)
$cbCursor.Checked = $true
$groupBox.Controls.Add($cbCursor)

$cbWindsurf = New-Object System.Windows.Forms.CheckBox
$cbWindsurf.Text = "Windsurf (Codeium)"
$cbWindsurf.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbWindsurf.Location = New-Object System.Drawing.Point(265, 58)
$cbWindsurf.Size = New-Object System.Drawing.Size(235, 24)
$cbWindsurf.Checked = $true
$groupBox.Controls.Add($cbWindsurf)

$cbVSCode = New-Object System.Windows.Forms.CheckBox
$cbVSCode.Text = "VS Code (Copilot / Cline / Roo Code)"
$cbVSCode.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbVSCode.Location = New-Object System.Drawing.Point(18, 90)
$cbVSCode.Size = New-Object System.Drawing.Size(235, 24)
$cbVSCode.Checked = $true
$groupBox.Controls.Add($cbVSCode)

$cbAntigravity = New-Object System.Windows.Forms.CheckBox
$cbAntigravity.Text = "Google Antigravity & Gemini CLI"
$cbAntigravity.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbAntigravity.Location = New-Object System.Drawing.Point(265, 90)
$cbAntigravity.Size = New-Object System.Drawing.Size(235, 24)
$cbAntigravity.Checked = $true
$groupBox.Controls.Add($cbAntigravity)

$cbContinue = New-Object System.Windows.Forms.CheckBox
$cbContinue.Text = "Perplexity / Continue.dev / LM Studio"
$cbContinue.Font = New-Object System.Drawing.Font("Segoe UI", 9.0)
$cbContinue.Location = New-Object System.Drawing.Point(18, 122)
$cbContinue.Size = New-Object System.Drawing.Size(280, 24)
$cbContinue.Checked = $false
$groupBox.Controls.Add($cbContinue)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Select your AI clients above and click Install."
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9.2)
$statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(71, 85, 105)
$statusLabel.Location = New-Object System.Drawing.Point(25, 326)
$statusLabel.Size = New-Object System.Drawing.Size(515, 24)
$form.Controls.Add($statusLabel)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(25, 354)
$progressBar.Size = New-Object System.Drawing.Size(515, 22)
$progressBar.Minimum = 0
$progressBar.Maximum = 100
$progressBar.Value = 0
$form.Controls.Add($progressBar)

$installBtn = New-Object System.Windows.Forms.Button
$installBtn.Text = "Install to Selected AI Clients"
$installBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$installBtn.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$installBtn.ForeColor = [System.Drawing.Color]::White
$installBtn.FlatStyle = "Flat"
$installBtn.Location = New-Object System.Drawing.Point(25, 392)
$installBtn.Size = New-Object System.Drawing.Size(515, 50)
$installBtn.Cursor = [System.Windows.Forms.Cursors]::Hand

$installBtn.Add_Click({
    $selectedList = @()
    if ($cbCodex.Checked) { $selectedList += "codex" }
    if ($cbClaude.Checked) { $selectedList += "claude" }
    if ($cbCursor.Checked) { $selectedList += "cursor" }
    if ($cbWindsurf.Checked) { $selectedList += "windsurf" }
    if ($cbVSCode.Checked) { $selectedList += "vscode" }
    if ($cbAntigravity.Checked) { $selectedList += "antigravity" }
    if ($cbContinue.Checked) { $selectedList += "continue" }

    if ($selectedList.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Please select at least one AI application.", "No Client Selected")
        return
    }
    $SelectedClientsStr = $selectedList -join ","

    $installBtn.Enabled = $false
    $installBtn.Text = "Installing... Please wait"
    $installBtn.BackColor = [System.Drawing.Color]::FromArgb(100, 116, 139)
    $form.Refresh()

    try {
        $statusLabel.Text = "Step 1/4: Checking Python runtime manager (uv)..."
        $progressBar.Value = 20
        $form.Refresh()

        $UvExe = $null
        foreach ($p in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:LOCALAPPDATA\uv\uv.exe")) {
            if (Test-Path $p) { $UvExe = $p; break }
        }
        if (-not $UvExe) {
            $cmd = Get-Command uv -ErrorAction SilentlyContinue
            if ($cmd) { $UvExe = $cmd.Source }
        }
        if (-not $UvExe) {
            powershell -WindowStyle Hidden -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
            $UvExe = "$env:USERPROFILE\.local\bin\uv.exe"
        }

        $statusLabel.Text = "Step 2/4: Preparing isolated Python 3.12 runtime..."
        $progressBar.Value = 50
        $form.Refresh()
        & $UvExe python install 3.12 | Out-Null

        $statusLabel.Text = "Step 3/4: Installing legal database & archive connectors..."
        $progressBar.Value = 75
        $form.Refresh()
        Push-Location $ScriptDir
        & $UvExe sync --python 3.12 | Out-Null
        Pop-Location

        $VenvPy = Join-Path $ScriptDir ".venv\Scripts\python.exe"
        $MainPy = Join-Path $ScriptDir "mcp_server_main.py"

        $statusLabel.Text = "Step 4/4: Registering MCP server in selected AI applications..."
        $progressBar.Value = 90
        $form.Refresh()

        & $VenvPy -c "
import json, os, pathlib, re
py_path = r'$VenvPy'
script_path = r'$MainPy'
repo = '$RepoName'
selected = '$SelectedClientsStr'.split(',')

client_map = {
    'codex': [pathlib.Path(os.environ.get('APPDATA', '')) / 'ChatGPT' / 'mcp.json'],
    'claude': [
        pathlib.Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json',
        pathlib.Path.home() / '.claude.json',
    ],
    'cursor': [pathlib.Path.home() / '.cursor' / 'mcp.json'],
    'windsurf': [pathlib.Path.home() / '.codeium' / 'windsurf' / 'mcp_config.json'],
    'vscode': [
        pathlib.Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'mcp.json',
        pathlib.Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'saoudrizwan.claude-dev' / 'settings' / 'cline_mcp_settings.json',
        pathlib.Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings' / 'mcp_settings.json',
    ],
    'antigravity': [
        pathlib.Path.home() / '.gemini' / 'config' / 'mcp_config.json',
        pathlib.Path.home() / '.gemini' / 'antigravity' / 'mcp_config.json',
        pathlib.Path.home() / '.gemini' / 'settings.json',
    ],
    'continue': [pathlib.Path.home() / '.continue' / 'mcpServers' / f'{repo}.json'],
}

for key in selected:
    if key == 'codex':
        codex_toml = pathlib.Path.home() / '.codex' / 'config.toml'
        try:
            codex_toml.parent.mkdir(parents=True, exist_ok=True)
            existing = codex_toml.read_text(encoding='utf-8') if codex_toml.exists() else ''
            esc_py = py_path.replace('\\', '\\\\')
            esc_sc = script_path.replace('\\', '\\\\')
            block = f'[mcp_servers.{repo}]\ncommand = "{esc_py}"\nargs = ["{esc_sc}"]\n'
            pattern = rf'(?ms)^\[mcp_servers\.{re.escape(repo)}\].*?(?=^\[|\Z)'
            if re.search(pattern, existing):
                updated = re.sub(pattern, block + '\n', existing)
            else:
                updated = (existing.rstrip() + '\n\n' + block) if existing.strip() else block
            codex_toml.write_text(updated, encoding='utf-8')
        except Exception:
            pass
    for cfg in client_map.get(key, []):
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
        $progressBar.Value = 100
        $statusLabel.Text = "Setup Complete! Connected to your selected AI applications."
        $installBtn.Text = "Installation Complete - Close Window"
        $installBtn.BackColor = [System.Drawing.Color]::FromArgb(22, 163, 74)
        [System.Windows.Forms.MessageBox]::Show(
            "$CountryName Legal MCP Server ($RepoName) has been installed and connected to your selected AI application(s).`r`n`r`nPlease restart your AI application to begin using the tools.",
            "JurisAtlas - Setup Complete",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
        $form.Close()
    } catch {
        $installBtn.Enabled = $true
        $installBtn.Text = "Retry Installation"
        $installBtn.BackColor = [System.Drawing.Color]::FromArgb(220, 38, 38)
        [System.Windows.Forms.MessageBox]::Show(
            "An error occurred during setup: $_",
            "Setup Error",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
    }
})

$form.Controls.Add($installBtn)
[void]$form.ShowDialog()
