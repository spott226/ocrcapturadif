[CmdletBinding()]
param([int]$Puerto = 8000)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Raiz

if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'Primero ejecute INSTALAR_IIS.ps1 o cree el entorno .venv.'
}
if (-not (Test-Path -LiteralPath '.\.env')) {
    throw 'Falta .env. Ejecute INSTALAR_IIS.ps1 o copie .env.servidor.example y complételo.'
}

Write-Host "Prueba local en http://127.0.0.1:$Puerto" -ForegroundColor Green
Write-Host 'Presione Ctrl+C para detenerla.'
$env:COOKIE_SECURE = 'false'
$env:FORCE_HTTPS = 'false'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port $Puerto
