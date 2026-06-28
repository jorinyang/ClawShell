# ClawShell Local — One-Command Installer (Windows PowerShell)
#
# Usage (PowerShell as Administrator):
#   iwr https://raw.githubusercontent.com/jorinyang/ClawShell/main/install.ps1 | iex
#
# Or download and run:
#   .\install.ps1
#
# After install:
#   clawshell-local                 # Start API + Web UI → opens browser
#   clawshell-local --web-only      # Just the web interface
#   clawshell-local --api-only      # Just the API server
param(
    [string]$InstallDir = "$env:USERPROFILE\.clawshell",
    [switch]$SkipNode = $false
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/jorinyang/ClawShell.git"

function Write-Step { Write-Host "[clawshell]" -ForegroundColor Green -NoNewline; Write-Host " $args" }
function Write-Warn { Write-Host "[clawshell] WARNING:" -ForegroundColor Yellow; Write-Host " $args" }
function Write-Err  { Write-Host "[clawshell] ERROR:" -ForegroundColor Red; Write-Host " $args" }

Write-Step ""
Write-Step "========================================="
Write-Step "  ClawShell Local v3.0 — Windows Installer"
Write-Step "========================================="
Write-Step ""

# ── Check Python ────────────────────────────────────────────
$python = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $v = & $cmd --version 2>$null
        if ($v -match "3\.(\d+)") {
            if ([int]$Matches[1] -ge 10) {
                $python = $cmd
                Write-Step "Python 3.10+ found: $v"
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Err "Python 3.10+ required but not found."
    Write-Err "Install from: https://www.python.org/downloads/"
    Write-Err "Check 'Add Python to PATH' during installation."
    exit 1
}

# ── Check Git ───────────────────────────────────────────────
try {
    $gitVer = & git --version 2>$null
    Write-Step "Git found: $gitVer"
} catch {
    Write-Err "Git required but not found."
    Write-Err "Install from: https://git-scm.com/download/win"
    exit 1
}

# ── Check Node.js (optional but recommended) ────────────────
$nodeOk = $false
if (-not $SkipNode) {
    try {
        $nodeVer = & node --version 2>$null
        Write-Step "Node.js found: $nodeVer"
        $nodeOk = $true
    } catch {
        Write-Warn "Node.js not found. Web UI requires Node.js."
        Write-Warn "Install from: https://nodejs.org (LTS recommended)"
        Write-Warn "Or use --api-only mode: clawshell-local --api-only"
    }
}

# ── Clone Repository ────────────────────────────────────────
if (Test-Path "$InstallDir\.git") {
    Write-Step "Repository exists, updating..."
    Push-Location $InstallDir
    git pull --ff-only origin main 2>$null
    Pop-Location
} else {
    Write-Step "Cloning ClawShell..."
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    git clone $RepoUrl $InstallDir
}

# ── Install Python Package ──────────────────────────────────
Write-Step "Installing Python package..."
Push-Location $InstallDir
try {
    & $python -m pip install --quiet -e . 2>$null
} catch {
    Write-Warn "pip install failed, trying user install..."
    & $python -m pip install --user --quiet -e . 2>$null
}
Pop-Location
Write-Step "Python package installed."

# ── Install Web Dependencies ────────────────────────────────
if ($nodeOk) {
    $webDir = "$InstallDir\web"
    if (Test-Path "$webDir\package.json") {
        Write-Step "Installing web dependencies (npm install)..."
        Push-Location $webDir
        if (-not (Test-Path "node_modules")) {
            npm install --silent 2>$null
        }

        Write-Step "Building Next.js frontend..."
        npx next build 2>$null
        Pop-Location
        Write-Step "Web frontend built."
    }
}

# ── Add to PATH hint ────────────────────────────────────────
Write-Step ""
Write-Step "========================================="
Write-Step "  Installation Complete!"
Write-Step ""
Write-Step "  Location: $InstallDir"
Write-Step ""

if ($nodeOk) {
    Write-Step "  Quick Start:"
    Write-Host "    clawshell-local              # Start API + Web UI -> browser opens"
    Write-Host "    clawshell-local --web-only   # Just the web interface"
    Write-Host "    clawshell-local --api-only   # Just the API server"
} else {
    Write-Step "  Quick Start (API only):"
    Write-Host "    clawshell-local --api-only   # Start local API on :8000"
}

Write-Step ""
if ($nodeOk) {
    Write-Step "  The browser will open http://localhost:3456/login"
} else {
    Write-Step "  API available at http://localhost:8000"
    Write-Step "  Swagger docs: http://localhost:8000/docs"
}
Write-Step "  Register a new account or login to get started."
Write-Step ""
