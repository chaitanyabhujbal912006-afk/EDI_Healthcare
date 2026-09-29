# run_dev.ps1 - EdiPro Developer Gateway Launcher
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Starting EdiPro EDI Healthcare Gateway " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$Root = $PSScriptRoot
$VenvPython = Join-Path $Root "venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[*] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv (Join-Path $Root "venv")
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $Root "src\backend\requirements.txt")
}

Write-Host "[+] Launching FastAPI gateway on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "[+] Operator Dashboard: http://localhost:8000/" -ForegroundColor Green
Write-Host "[i] Press Ctrl+C to terminate." -ForegroundColor Yellow

$BackendDir = Join-Path $Root "src\backend"
Set-Location $BackendDir
& $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
