[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Raiz

foreach ($Archivo in @('.env', 'web.config', 'requirements.txt', '.venv\Scripts\python.exe')) {
    if (-not (Test-Path -LiteralPath $Archivo)) { throw "Falta $Archivo" }
}

try { [xml](Get-Content -LiteralPath 'web.config' -Raw) | Out-Null }
catch { throw 'web.config no es XML válido.' }

& '.\.venv\Scripts\python.exe' 'tools\verificar_servidor.py'
if ($LASTEXITCODE -ne 0) { throw 'Falló la verificación de Python, OCR o base de datos.' }

Import-Module WebAdministration -ErrorAction SilentlyContinue
if (Get-Module WebAdministration) {
    if (-not (Get-WebGlobalModule | Where-Object Name -eq 'httpPlatformHandler')) {
        throw 'IIS no tiene registrado HttpPlatformHandler.'
    }
}

Write-Host 'VERIFICACIÓN CORRECTA. Falta confirmar HTTPS, inicio de sesión y una captura ficticia desde el teléfono.' -ForegroundColor Green
