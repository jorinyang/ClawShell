# ClawShell Edge — PowerShell installer for Windows
Write-Host "ClawShell 2.0 Edge Brain Installer" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    exit 1
}

Write-Host "Python: $(python --version)"

# Install from GitHub
Write-Host "Installing from GitHub..."
pip install git+https://github.com/jorinyang/ClawShell.git

Write-Host ""
Write-Host "ClawShell Edge installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Configure:   clawshell-edge config --cloud-url https://your-cloud:8000"
Write-Host "  2. Start sync:  clawshell-edge start"
Write-Host "  3. Check status: clawshell-edge status"
