[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Raiz

function Confirmar-VCRuntimeX64 {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'Este paquete requiere Windows x64.'
    }

    $Registrado = $false
    $Version = 'desconocida'
    $BaseRegistro = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry64
    )
    $ClaveRegistro = $null
    try {
        $ClaveRegistro = $BaseRegistro.OpenSubKey('SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64')
        if ($ClaveRegistro) {
            $Registrado = [int]$ClaveRegistro.GetValue('Installed', 0) -eq 1
            $VersionDetectada = [string]$ClaveRegistro.GetValue('Version', '')
            if ($VersionDetectada) { $Version = $VersionDetectada }
        }
    }
    finally {
        if ($ClaveRegistro) { $ClaveRegistro.Dispose() }
        $BaseRegistro.Dispose()
    }

    $DirectorioSistema = if ([Environment]::Is64BitProcess) {
        Join-Path $env:WINDIR 'System32'
    }
    else {
        Join-Path $env:WINDIR 'Sysnative'
    }
    $DllsFaltantes = @()
    foreach ($Dll in @('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll')) {
        if (-not (Test-Path -LiteralPath (Join-Path $DirectorioSistema $Dll))) {
            $DllsFaltantes += $Dll
        }
    }

    if (-not $Registrado -or $DllsFaltantes.Count -gt 0) {
        $Detalle = if ($DllsFaltantes.Count -gt 0) {
            ' DLL faltantes: ' + ($DllsFaltantes -join ', ') + '.'
        }
        else { '' }
        throw (
            'Falta Microsoft Visual C++ Redistributable v14 x64 (2015-2022), requerido por ONNX Runtime/RapidOCR.' +
            $Detalle + ' Descárguelo manualmente desde Microsoft: ' +
            'https://aka.ms/vs/17/release/vc_redist.x64.exe . Instálelo, reinicie si se solicita y vuelva a ejecutar ' +
            'VERIFICAR_SERVIDOR.ps1. Este script no descarga ni instala ese componente.'
        )
    }

    Write-Host "Microsoft Visual C++ Redistributable x64 detectado ($Version)." -ForegroundColor DarkGreen
}

Confirmar-VCRuntimeX64

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
