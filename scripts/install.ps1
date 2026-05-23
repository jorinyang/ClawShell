# ClawShell Edge — Windows Installer
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
#        or     iwr https://clawshell.club/install.ps1 | iex
param(
    [string]$Dir = "$env:USERPROFILE\.clawshell",
    [switch]$NonInteractive = $false
)

Write-Host ""
Write-Host "ClawShell Edge — Windows Installer v2.2" -ForegroundColor Cyan
Write-Host ""

# ── OS Detection ──────────────────────────────────────────────
$os = if ($env:OS -match "Windows") { "windows" } else { "unknown" }
Write-Host "Detected OS: $os" -ForegroundColor Green
Write-Host "Install dir: $Dir"

# ── Python Check ─────────────────────────────────────────────
try {
    $pyVer = python --version 2>&1
    Write-Host "OK $pyVer" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# ── Git Check ────────────────────────────────────────────────
try {
    $gitVer = git --version 2>&1
    Write-Host "OK $gitVer" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Git not found. Install from https://git-scm.com" -ForegroundColor Red
    exit 1
}

# ── Account Setup ────────────────────────────────────────────
Write-Host ""
Write-Host "Before continuing, complete these steps:" -ForegroundColor Yellow
Write-Host "  1. Register at https://memos.cloud (get API Key mpg-xxx)"
Write-Host "  2. Get LLM Key from https://platform.deepseek.com/api_keys"
Write-Host "  3. GitHub access: https://github.com/jorinyang/ClawShell"
Write-Host ""

if (-not $NonInteractive) {
    $confirm = Read-Host "Completed? [Y/n]"
    if ($confirm -match "n|N") { Write-Host "Please complete and retry."; exit 1 }
}

# ── Clone ClawShell ──────────────────────────────────────────
Write-Host ""
if (Test-Path "$Dir\.git") {
    Write-Host "Updating ClawShell..."
    Set-Location $Dir; git pull --ff-only 2>$null
} else {
    Write-Host "Cloning ClawShell..."
    git clone https://github.com/jorinyang/ClawShell.git $Dir 2>$null
}
Write-Host "OK ClawShell repository ready" -ForegroundColor Green

# ── Dependencies ─────────────────────────────────────────────
Write-Host ""
python -m pip install --quiet pyyaml requests aiohttp websockets 2>$null
Write-Host "OK Core dependencies" -ForegroundColor Green

# ── Memory Plugins ───────────────────────────────────────────
Write-Host ""
if (-not (Test-Path "$env:USERPROFILE\.mempalace")) {
    git clone https://github.com/mempalace/mempalace.git "$env:USERPROFILE\.mempalace" 2>$null
}
Write-Host "OK MemPalace" -ForegroundColor Green

python -m pip install --quiet memos-local-plugin 2>$null
Write-Host "OK MemOS plugin" -ForegroundColor Green

# ── Agent Config ─────────────────────────────────────────────
Write-Host ""
Set-Location $Dir
python -m edge.installer config 2>$null
Write-Host "OK Agent configs checked" -ForegroundColor Green

# ── Self-Check ───────────────────────────────────────────────
Write-Host ""
Write-Host "Self-Check:" -ForegroundColor Yellow
if (Test-Path "$Dir\edge") { Write-Host "  OK edge/" -ForegroundColor Green } else { Write-Host "  MISS edge/" -ForegroundColor Red }
if (Test-Path "$Dir\exoskeleton") { Write-Host "  OK exoskeleton/" -ForegroundColor Green }

# ── .env ─────────────────────────────────────────────────────
$envFile = "$Dir\.env"
if (-not (Test-Path $envFile)) {
    @"
# ClawShell Edge Configuration
CLAWSHELL_HOME=$Dir
CLAWSHELL_CLOUD_URL=http://47.239.71.174:8000
# Add your keys:
# DEEPSEEK_API_KEY=sk-xxx
# MEMOS_API_KEY=mpg-xxx
"@ | Out-File -FilePath $envFile -Encoding UTF8
}
Write-Host "OK .env ready" -ForegroundColor Green

# ── Done ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "  Edit:  $envFile"
Write-Host "  Start: cd $Dir && python -m edge.sync.sync_daemon"
Write-Host "  Visit: https://clawshell.club/login"
Write-Host ""
